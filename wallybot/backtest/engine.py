"""BacktestEngine: single-instrument, single-strategy, long-only replay over historical candles
with an explicit fill/cost model, per ARCHITECTURE.md's Phase 5 bullet: "Implementar backtesting
con modelo de fills y costes explícito; compartir reglas verificables con PAPER."

Fill assumption, stated plainly rather than hidden in a formula: this codebase's Parquet store
(ADR-005) only records OHLCV candles, not order book depth or bid/ask -- there is no real spread
to simulate against. A signal computed as-of a candle's `close_time` (using only that candle and
everything before it -- `FeatureEngine.compute` already raises `LookaheadError` if it were ever
handed a later one) fills at the *next* candle's open price. `BacktestCostModel.fee_rate` reuses
`FakeExchange`'s own default (0.001) so PAPER and backtests share one fee assumption instead of
two independently invented ones; `slippage_pct` has no PAPER equivalent to share (FakeExchange
simulates a real bid/ask spread instead) and is an explicitly-labeled placeholder, not a
calibrated cost -- same honesty this codebase already applies to `smart_money.py`'s 60/40 split.

Deliberately out of scope: multi-asset/multi-strategy portfolios, risk-engine sizing (this
allocates a fixed `allocation_pct` of current equity per trade, nothing else), short selling
(`Action.SELL` only ever exits an existing long, matching `DecisionPipeline`'s own "SELL is not
yet supported" limit), walk-forward or Monte Carlo evaluation (Phase 5 Slice 3).

Cash amounts (equity, fees, proceeds, cost basis) are quantized to `_CASH_PRECISION` (cents) after
every step, and fill prices/quantities to the traded instrument's own `price_increment`/
`quantity_increment` (same `.quantize()` convention `FakeExchange`/`deterministic_risk_engine`
already use) -- quantity always rounds down, never claiming more was bought than the notional
actually covers. Without this, unquantized `Decimal` division (`notional / fill_price`) carries
its full ~28-digit context precision through every subsequent multiplication, compounding into a
`final_equity` like "10999.93099135968523141293843" -- a real bug found from a user-reported
screenshot, not a hypothetical.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from wallybot.domain.features import FeatureEngine
from wallybot.domain.market import Candle, Instrument
from wallybot.domain.regime import classify_regime
from wallybot.domain.strategy import Action, Strategy, StrategyContext

BACKTEST_ENGINE_VERSION = 1
_FAKE_EXCHANGE_DEFAULT_FEE_RATE = Decimal("0.001")
_CASH_PRECISION = Decimal("0.01")


@dataclass(frozen=True)
class BacktestCostModel:
    fee_rate: Decimal = _FAKE_EXCHANGE_DEFAULT_FEE_RATE
    slippage_pct: Decimal = Decimal("0.0005")

    def __post_init__(self) -> None:
        if not (Decimal(0) <= self.fee_rate <= Decimal(1)):
            raise ValueError("fee_rate must be between 0 and 1")
        if not (Decimal(0) <= self.slippage_pct <= Decimal(1)):
            raise ValueError("slippage_pct must be between 0 and 1")


@dataclass(frozen=True)
class BacktestTrade:
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    fees_paid: Decimal
    pnl: Decimal


@dataclass(frozen=True)
class BacktestResult:
    instrument: Instrument
    version: int
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[tuple[datetime, Decimal], ...]
    starting_equity: Decimal
    final_equity: Decimal

    @property
    def total_return_pct(self) -> Decimal:
        return (self.final_equity - self.starting_equity) / self.starting_equity

    @property
    def max_drawdown_pct(self) -> Decimal:
        peak = self.starting_equity
        worst = Decimal(0)
        for _, equity in self.equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak
            worst = max(worst, drawdown)
        return worst

    @property
    def win_rate(self) -> Decimal | None:
        if not self.trades:
            return None
        wins = sum(1 for trade in self.trades if trade.pnl > 0)
        return Decimal(wins) / Decimal(len(self.trades))


class BacktestEngine:
    def __init__(
        self,
        feature_engine: FeatureEngine,
        strategy: Strategy,
        cost_model: BacktestCostModel,
        feature_window: int,
        risk_off_threshold: Decimal,
    ) -> None:
        if feature_window < 1:
            raise ValueError("feature_window must be positive")
        self.feature_engine = feature_engine
        self.strategy = strategy
        self.cost_model = cost_model
        self.feature_window = feature_window
        self.risk_off_threshold = risk_off_threshold

    def run(
        self, candles: list[Candle], starting_equity: Decimal, allocation_pct: Decimal
    ) -> BacktestResult:
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        if not (Decimal(0) < allocation_pct <= Decimal(1)):
            raise ValueError("allocation_pct must be between 0 (exclusive) and 1")
        ordered = sorted(candles, key=lambda c: c.open_time)
        if len(ordered) < self.feature_window + 2:
            raise ValueError(
                f"need at least {self.feature_window + 2} candles "
                f"(feature_window + one to signal on + one to fill against), got {len(ordered)}"
            )
        instrument = ordered[0].instrument
        for candle in ordered:
            if candle.instrument != instrument:
                raise ValueError("all candles must share the same instrument")
        if instrument.price_increment is None or instrument.quantity_increment is None:
            # Fail closed on missing precision, per Instrument's own docstring -- never guess a
            # tick/lot size. Every real caller resolves candles from Kraken (full precision) or
            # from a persisted ExperimentRecord (wallybot.application.research_runner), never from
            # Tiingo (whose crypto metadata never reports these, by design).
            raise ValueError(f"{instrument.id} has no price/quantity precision to backtest with")

        equity = starting_equity
        equity_curve: list[tuple[datetime, Decimal]] = [(ordered[0].open_time, equity)]
        trades: list[BacktestTrade] = []
        position_quantity: Decimal | None = None
        position_entry_price: Decimal | None = None
        position_entry_time: datetime | None = None

        for i in range(self.feature_window - 1, len(ordered) - 1):
            window = ordered[: i + 1]
            signal_candle = ordered[i]
            fill_candle = ordered[i + 1]

            vector = self.feature_engine.compute(
                window, signal_candle.close_time, self.feature_window
            )
            regime = classify_regime(vector, self.risk_off_threshold)
            signal = self.strategy.evaluate(
                StrategyContext(
                    instrument=instrument,
                    features=vector,
                    regime=regime,
                    as_of=signal_candle.close_time,
                )
            )

            in_position = position_quantity is not None
            if signal.action is Action.BUY and not in_position:
                fill_price = (
                    fill_candle.open * (Decimal(1) + self.cost_model.slippage_pct)
                ).quantize(instrument.price_increment)
                notional = equity * allocation_pct
                quantity = (notional / fill_price).quantize(
                    instrument.quantity_increment, rounding=ROUND_DOWN
                )
                fee = (notional * self.cost_model.fee_rate).quantize(_CASH_PRECISION)
                equity = (equity - fee).quantize(_CASH_PRECISION)
                position_quantity = quantity
                position_entry_price = fill_price
                position_entry_time = fill_candle.open_time
            elif signal.action is Action.SELL and in_position:
                assert position_quantity is not None
                assert position_entry_price is not None
                assert position_entry_time is not None
                fill_price = (
                    fill_candle.open * (Decimal(1) - self.cost_model.slippage_pct)
                ).quantize(instrument.price_increment)
                proceeds = (position_quantity * fill_price).quantize(_CASH_PRECISION)
                fee = (proceeds * self.cost_model.fee_rate).quantize(_CASH_PRECISION)
                cost_basis = (position_quantity * position_entry_price).quantize(_CASH_PRECISION)
                pnl = proceeds - fee - cost_basis
                equity = (equity + proceeds - fee).quantize(_CASH_PRECISION)
                trades.append(
                    BacktestTrade(
                        entry_time=position_entry_time,
                        exit_time=fill_candle.open_time,
                        entry_price=position_entry_price,
                        exit_price=fill_price,
                        quantity=position_quantity,
                        fees_paid=fee,
                        pnl=pnl,
                    )
                )
                position_quantity = None
                position_entry_price = None
                position_entry_time = None

            mark_to_market = equity
            if position_quantity is not None:
                mark_to_market = (equity + position_quantity * fill_candle.close).quantize(
                    _CASH_PRECISION
                )
            equity_curve.append((fill_candle.close_time, mark_to_market))

        final_equity = equity_curve[-1][1]
        return BacktestResult(
            instrument=instrument,
            version=BACKTEST_ENGINE_VERSION,
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            starting_equity=starting_equity,
            final_equity=final_equity,
        )
