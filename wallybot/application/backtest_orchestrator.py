"""BacktestOrchestrator: wires Slice 1 (`read_candles`) -> Slice 2 (`BacktestEngine`) -> Slice 3
(optional bootstrap resampling) into the one real path from a requested dataset window to a
comparable backtest outcome -- the end-to-end composition every earlier Phase 5 slice's own
"Explicitly not built" section flagged as missing ("no code that actually calls
BacktestEngine/ExperimentRepository together end-to-end").

Persistence is deliberately NOT this orchestrator's job: like `ShadowDecisionService`, it returns
a pure `ExperimentRecord` for the caller (the API route, which already owns a DB session) to
persist via `ExperimentRepository` -- keeping this class DB-free and unit-testable the same way
Slices 1-3 already are.

Only `wallybot.strategies.trend_following.TrendFollowingStrategy` /
`wallybot.features.simple.SimpleFeatureEngine` are wired: this codebase has exactly one strategy
and one feature engine so far. A registry over more than one is `PHASE_5.md`'s remaining "strategy
registry lifecycle" bullet, not built here.

The `Instrument` is looked up from the injected `MarketDataProvider` (the same real venue
precision data `DecisionPipeline` already trusts), never fabricated from caller-supplied numbers --
the exact mistake `historical_query.py`'s own docstring documents avoiding. `run()` accepts an
optional pre-resolved `Instrument` instead, for the one caller that cannot reach a live adapter at
all: an isolated research re-run (wallybot.infrastructure.jobs, no internet egress) reconstructs it
from the original `ExperimentRecord`'s own stored identity/precision rather than skip validation --
still never fabricated, just sourced from an earlier real discovery instead of a fresh one.

`read_candles` is a synchronous, blocking DuckDB call (file I/O + query) -- run via
`asyncio.to_thread` so it never blocks the event loop this orchestrator's `run()` is awaited on.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from wallybot.backtest.engine import BacktestCostModel, BacktestEngine, BacktestResult
from wallybot.backtest.evaluation import BootstrapResult, bootstrap_trade_pnls
from wallybot.data.historical_query import QueryResourceLimits, read_candles
from wallybot.domain.clock import Clock
from wallybot.domain.experiment import ExperimentRecord
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import Instrument, MarketDataProvider
from wallybot.features.simple import FEATURE_VERSION, SimpleFeatureEngine
from wallybot.strategies.trend_following import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    TrendFollowingStrategy,
)

DEFAULT_BOOTSTRAP_SAMPLES = 2000


class InstrumentNotFound(ValueError):
    """No instrument matching the requested base/quote was discovered by the provider."""


class InsufficientHistoricalData(ValueError):
    """The requested dataset window has too few checksummed candles to backtest."""


@dataclass(frozen=True)
class BacktestRequest:
    instrument_base: str
    instrument_quote: str
    timeframe: str
    window_start: datetime
    window_end: datetime
    feature_window: int
    risk_off_threshold: Decimal
    starting_equity: Decimal
    allocation_pct: Decimal
    fee_rate: Decimal
    slippage_pct: Decimal
    bootstrap_seed: int | None = None
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES


@dataclass(frozen=True)
class BacktestOutcome:
    record: ExperimentRecord
    result: BacktestResult
    bootstrap: BootstrapResult | None


class BacktestOrchestrator:
    def __init__(
        self,
        provider: MarketDataProvider | None,
        data_root: Path,
        resource_limits: QueryResourceLimits,
        clock: Clock,
        id_generator: IdGenerator,
    ) -> None:
        self.provider = provider
        self.data_root = data_root
        self.resource_limits = resource_limits
        self.clock = clock
        self.id_generator = id_generator

    async def run(
        self, request: BacktestRequest, instrument: Instrument | None = None
    ) -> BacktestOutcome:
        if instrument is None:
            if self.provider is None:
                raise InstrumentNotFound(
                    "no MarketDataProvider configured and no Instrument supplied"
                )
            instruments = await self.provider.discover_instruments()
            instrument = next(
                (
                    candidate
                    for candidate in instruments
                    if candidate.base == request.instrument_base
                    and candidate.quote == request.instrument_quote
                ),
                None,
            )
            if instrument is None:
                raise InstrumentNotFound(
                    f"no instrument discovered for "
                    f"{request.instrument_base}/{request.instrument_quote}"
                )

        candles = await asyncio.to_thread(
            read_candles,
            self.data_root,
            instrument,
            request.timeframe,
            request.window_start,
            request.window_end,
            self.resource_limits,
        )

        engine = BacktestEngine(
            feature_engine=SimpleFeatureEngine(),
            strategy=TrendFollowingStrategy(),
            cost_model=BacktestCostModel(
                fee_rate=request.fee_rate, slippage_pct=request.slippage_pct
            ),
            feature_window=request.feature_window,
            risk_off_threshold=request.risk_off_threshold,
        )
        try:
            result = engine.run(candles, request.starting_equity, request.allocation_pct)
        except ValueError as exc:
            raise InsufficientHistoricalData(str(exc)) from exc

        bootstrap = None
        if request.bootstrap_seed is not None:
            bootstrap = bootstrap_trade_pnls(
                result, request.bootstrap_samples, request.bootstrap_seed
            )

        record = ExperimentRecord(
            experiment_id=self.id_generator.new_id(),
            strategy_id=STRATEGY_ID,
            strategy_version=STRATEGY_VERSION,
            feature_engine_version=FEATURE_VERSION,
            backtest_engine_version=result.version,
            instrument_venue=instrument.venue,
            instrument_market_type=str(instrument.market_type),
            instrument_base=instrument.base,
            instrument_quote=instrument.quote,
            price_increment=instrument.price_increment,
            quantity_increment=instrument.quantity_increment,
            min_quantity=instrument.min_quantity,
            timeframe=request.timeframe,
            window_start=request.window_start,
            window_end=request.window_end,
            feature_window=request.feature_window,
            risk_off_threshold=request.risk_off_threshold,
            fee_rate=engine.cost_model.fee_rate,
            slippage_pct=engine.cost_model.slippage_pct,
            starting_equity=request.starting_equity,
            allocation_pct=request.allocation_pct,
            seed=request.bootstrap_seed,
            trade_count=len(result.trades),
            final_equity=result.final_equity,
            total_return_pct=result.total_return_pct,
            max_drawdown_pct=result.max_drawdown_pct,
            win_rate=result.win_rate,
            created_at=self.clock.now(),
        )
        return BacktestOutcome(record=record, result=result, bootstrap=bootstrap)
