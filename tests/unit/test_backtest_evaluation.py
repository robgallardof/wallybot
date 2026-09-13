from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.backtest.engine import (
    BacktestCostModel,
    BacktestEngine,
    BacktestResult,
    BacktestTrade,
)
from wallybot.backtest.evaluation import bootstrap_trade_pnls, run_walk_forward
from wallybot.domain.market import Candle, Instrument, MarketType
from wallybot.features.simple import SimpleFeatureEngine
from wallybot.strategies.trend_following import TrendFollowingStrategy

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
START = datetime(2026, 1, 1, tzinfo=UTC)
NO_COST = BacktestCostModel(fee_rate=Decimal(0), slippage_pct=Decimal(0))


def make_engine() -> BacktestEngine:
    return BacktestEngine(
        feature_engine=SimpleFeatureEngine(),
        strategy=TrendFollowingStrategy(),
        cost_model=NO_COST,
        feature_window=3,
        risk_off_threshold=Decimal("0.5"),
    )


def make_candles(prices: list[str]) -> list[Candle]:
    candles = []
    for i, price in enumerate(prices):
        open_time = START + timedelta(hours=i)
        candles.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=Decimal(price),
                high=Decimal(price),
                low=Decimal(price),
                close=Decimal(price),
                volume=Decimal("10"),
                source="fake",
                received_at=open_time + timedelta(hours=1),
            )
        )
    return candles


def make_trade(pnl: str) -> BacktestTrade:
    return BacktestTrade(
        entry_time=START,
        exit_time=START + timedelta(hours=1),
        entry_price=Decimal("100"),
        exit_price=Decimal("101"),
        quantity=Decimal("1"),
        fees_paid=Decimal("0"),
        pnl=Decimal(pnl),
    )


def make_result(pnls: list[str]) -> BacktestResult:
    return BacktestResult(
        instrument=INSTRUMENT,
        version=1,
        trades=tuple(make_trade(p) for p in pnls),
        equity_curve=((START, Decimal("10000")),),
        starting_equity=Decimal("10000"),
        final_equity=Decimal("10000") + sum((Decimal(p) for p in pnls), Decimal(0)),
    )


def test_walk_forward_splits_into_the_requested_number_of_independent_windows() -> None:
    # 8 repeats of a 10-candle rise/fall cycle -> plenty of candles for 4 windows of 20 each.
    prices = ["100", "101", "102", "103", "104", "105", "104", "103", "102", "101"] * 8
    windows = run_walk_forward(
        make_engine(), make_candles(prices), Decimal("10000"), Decimal("1"), num_windows=4
    )
    assert len(windows) == 4
    assert [w.index for w in windows] == [0, 1, 2, 3]
    for window in windows:
        assert window.result.starting_equity == Decimal("10000")


def test_walk_forward_rejects_too_few_candles_per_window() -> None:
    prices = ["100", "101", "102", "103", "104"]
    with pytest.raises(ValueError, match="needs at least"):
        run_walk_forward(
            make_engine(), make_candles(prices), Decimal("10000"), Decimal("1"), num_windows=3
        )


def test_walk_forward_rejects_nonpositive_num_windows() -> None:
    prices = ["100"] * 20
    with pytest.raises(ValueError, match="num_windows"):
        run_walk_forward(
            make_engine(), make_candles(prices), Decimal("10000"), Decimal("1"), num_windows=0
        )


def test_bootstrap_returns_none_with_fewer_than_two_trades() -> None:
    assert bootstrap_trade_pnls(make_result([]), num_samples=100, seed=1) is None
    assert bootstrap_trade_pnls(make_result(["50"]), num_samples=100, seed=1) is None


def test_bootstrap_mean_converges_toward_the_actual_average_pnl() -> None:
    result = make_result(["100", "-50", "80", "-30", "60"])
    actual_mean = sum((t.pnl for t in result.trades), Decimal(0)) / len(result.trades)
    bootstrap = bootstrap_trade_pnls(result, num_samples=5000, seed=42)
    assert bootstrap is not None
    assert bootstrap.trades_per_sample == 5
    per_trade_mean = bootstrap.mean_total_pnl / bootstrap.trades_per_sample
    assert abs(per_trade_mean - actual_mean) < Decimal("5")
    assert bootstrap.p05_total_pnl <= bootstrap.median_total_pnl <= bootstrap.p95_total_pnl


def test_bootstrap_probability_of_loss_is_one_when_every_trade_lost() -> None:
    result = make_result(["-10", "-20", "-30"])
    bootstrap = bootstrap_trade_pnls(result, num_samples=200, seed=1)
    assert bootstrap is not None
    assert bootstrap.probability_of_loss == Decimal(1)


def test_bootstrap_is_deterministic_for_the_same_seed() -> None:
    result = make_result(["10", "-5", "20", "-15"])
    first = bootstrap_trade_pnls(result, num_samples=500, seed=7)
    second = bootstrap_trade_pnls(result, num_samples=500, seed=7)
    assert first == second


def test_bootstrap_rejects_nonpositive_num_samples() -> None:
    with pytest.raises(ValueError, match="num_samples"):
        bootstrap_trade_pnls(make_result(["10", "-5"]), num_samples=0, seed=1)
