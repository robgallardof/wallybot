from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.backtest.engine import BacktestCostModel, BacktestEngine
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
# Rises for a few candles (momentum > 0 -> BUY), flattens (HOLD), then falls (momentum < 0 -> SELL).
PRICES = ["100", "101", "102", "103", "104", "105", "104", "103", "102", "101", "100"]


def make_series() -> list[Candle]:
    candles = []
    for i, price in enumerate(PRICES):
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


NO_COST = BacktestCostModel(fee_rate=Decimal(0), slippage_pct=Decimal(0))


def make_engine(cost_model: BacktestCostModel = NO_COST) -> BacktestEngine:
    return BacktestEngine(
        feature_engine=SimpleFeatureEngine(),
        strategy=TrendFollowingStrategy(),
        cost_model=cost_model,
        feature_window=3,
        risk_off_threshold=Decimal("0.5"),
    )


def test_a_rise_then_fall_produces_exactly_one_round_trip_trade() -> None:
    result = make_engine().run(
        make_series(), starting_equity=Decimal("10000"), allocation_pct=Decimal("1")
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    # BUY signal first fires when momentum turns positive at index 2 (price 102); fill is the
    # *next* candle's open (index 3, price 103) -- never the signal candle's own price.
    assert trade.entry_price == Decimal("103")
    # SELL signal fires when momentum turns negative at index 7 (price 103); fill is index 8's
    # open (price 102).
    assert trade.exit_price == Decimal("102")
    assert trade.pnl < 0  # bought at 103, sold at 102, with zero costs


def test_fee_and_slippage_are_actually_applied_to_fill_prices_and_pnl() -> None:
    cost_model = BacktestCostModel(fee_rate=Decimal("0.01"), slippage_pct=Decimal("0.01"))
    result = make_engine(cost_model).run(
        make_series(), starting_equity=Decimal("10000"), allocation_pct=Decimal("1")
    )

    trade = result.trades[0]
    assert trade.entry_price == Decimal("103") * Decimal("1.01")
    assert trade.exit_price == Decimal("102") * Decimal("0.99")
    assert trade.fees_paid > 0

    no_cost_trade = (
        make_engine(NO_COST)
        .run(make_series(), starting_equity=Decimal("10000"), allocation_pct=Decimal("1"))
        .trades[0]
    )
    # Slippage plus fees always make the round trip strictly worse than the frictionless case.
    assert trade.pnl < no_cost_trade.pnl


def test_equity_curve_starts_at_starting_equity_and_has_one_point_per_evaluated_candle() -> None:
    result = make_engine().run(
        make_series(), starting_equity=Decimal("5000"), allocation_pct=Decimal("0.5")
    )
    assert result.equity_curve[0] == (START, Decimal("5000"))
    assert result.starting_equity == Decimal("5000")


def test_max_drawdown_is_nonnegative_and_zero_when_equity_never_falls_below_start() -> None:
    flat = []
    for i in range(6):
        open_time = START + timedelta(hours=i)
        flat.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=Decimal("100"),
                high=Decimal("100"),
                low=Decimal("100"),
                close=Decimal("100"),
                volume=Decimal("10"),
                source="fake",
                received_at=open_time + timedelta(hours=1),
            )
        )
    result = make_engine().run(flat, starting_equity=Decimal("1000"), allocation_pct=Decimal("1"))
    assert result.max_drawdown_pct == Decimal(0)
    assert result.trades == ()
    assert result.win_rate is None


def test_rejects_mixed_instruments() -> None:
    other = Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base="ETH",
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
    )
    series = make_series()
    mixed = [*series[:-1], replace(series[-1], instrument=other)]
    with pytest.raises(ValueError, match="same instrument"):
        make_engine().run(mixed, starting_equity=Decimal("1000"), allocation_pct=Decimal("1"))


def test_rejects_too_short_a_series() -> None:
    with pytest.raises(ValueError, match="need at least"):
        make_engine().run(
            make_series()[:3], starting_equity=Decimal("1000"), allocation_pct=Decimal("1")
        )


def test_rejects_nonpositive_starting_equity() -> None:
    with pytest.raises(ValueError, match="starting_equity"):
        make_engine().run(make_series(), starting_equity=Decimal(0), allocation_pct=Decimal("1"))


def test_rejects_allocation_pct_out_of_range() -> None:
    with pytest.raises(ValueError, match="allocation_pct"):
        make_engine().run(
            make_series(), starting_equity=Decimal("1000"), allocation_pct=Decimal("1.5")
        )


def test_cost_model_rejects_negative_fee_rate() -> None:
    with pytest.raises(ValueError, match="fee_rate"):
        BacktestCostModel(fee_rate=Decimal("-0.01"))


def test_final_equity_never_carries_more_precision_than_cents() -> None:
    # notional / fill_price (e.g. 10000 / 103) is a repeating decimal that, left unquantized,
    # carries Decimal's ~28-digit context precision through every later multiplication -- the
    # real bug this regression test guards (a user-reported "10999.93099135968523141293843 USD").
    cost_model = BacktestCostModel(fee_rate=Decimal("0.001"), slippage_pct=Decimal("0.0005"))
    result = make_engine(cost_model).run(
        make_series(), starting_equity=Decimal("10000"), allocation_pct=Decimal("1")
    )

    assert result.final_equity == result.final_equity.quantize(Decimal("0.01"))
    for _, equity in result.equity_curve:
        assert equity == equity.quantize(Decimal("0.01"))
    assert INSTRUMENT.price_increment is not None
    assert INSTRUMENT.quantity_increment is not None
    for trade in result.trades:
        assert trade.fees_paid == trade.fees_paid.quantize(Decimal("0.01"))
        assert trade.entry_price == trade.entry_price.quantize(INSTRUMENT.price_increment)
        assert trade.quantity == trade.quantity.quantize(INSTRUMENT.quantity_increment)


def test_rejects_an_instrument_with_no_precision_to_backtest_with() -> None:
    unpriced = Instrument(venue="fake", market_type=MarketType.SPOT, base="BTC", quote="USD")
    series = [replace(candle, instrument=unpriced) for candle in make_series()]
    with pytest.raises(ValueError, match="precision"):
        make_engine().run(series, starting_equity=Decimal("1000"), allocation_pct=Decimal("1"))
