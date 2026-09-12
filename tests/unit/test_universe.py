from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType
from wallybot.market.universe import (
    UniverseFilterConfig,
    eligible_instruments,
    evaluate_instrument,
    evaluate_universe,
)


def make_instrument(**overrides) -> Instrument:
    fields = {
        "venue": "fake",
        "market_type": MarketType.SPOT,
        "base": "BTC",
        "quote": "USD",
        "price_increment": Decimal("0.01"),
        "quantity_increment": Decimal("0.0001"),
        "min_quantity": Decimal("0.0001"),
    }
    fields.update(overrides)
    return Instrument(**fields)


def make_candles(
    instrument: Instrument, count: int, volume: Decimal, price: Decimal
) -> list[Candle]:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    for i in range(count):
        open_time = now - timedelta(hours=count - i)
        candles.append(
            Candle(
                instrument=instrument,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                source="fake",
                received_at=now,
            )
        )
    return candles


def make_snapshot(instrument: Instrument, spread_ratio: Decimal) -> MarketSnapshot:
    bid = Decimal("100")
    ask = bid / (1 - spread_ratio)
    return MarketSnapshot(
        instrument=instrument,
        bid=bid,
        ask=ask,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        source="fake",
    )


CONFIG = UniverseFilterConfig(
    version=1,
    min_history_candles=10,
    min_average_quote_volume=Decimal("1000"),
    max_spread_ratio=Decimal("0.01"),
)


def test_config_rejects_nonpositive_thresholds():
    with pytest.raises(ValueError):
        UniverseFilterConfig(
            version=1,
            min_history_candles=0,
            min_average_quote_volume=Decimal("1"),
            max_spread_ratio=Decimal("0.01"),
        )


def test_eligible_instrument_passes_all_filters():
    instrument = make_instrument()
    candles = make_candles(instrument, 10, volume=Decimal("100"), price=Decimal("100"))
    snapshot = make_snapshot(instrument, Decimal("0.001"))
    evaluation = evaluate_instrument(instrument, candles, snapshot, CONFIG)
    assert evaluation.eligible
    assert evaluation.reasons == ()


def test_rejects_insufficient_history():
    instrument = make_instrument()
    candles = make_candles(instrument, 3, volume=Decimal("100"), price=Decimal("100"))
    snapshot = make_snapshot(instrument, Decimal("0.001"))
    evaluation = evaluate_instrument(instrument, candles, snapshot, CONFIG)
    assert not evaluation.eligible
    assert "insufficient_history" in evaluation.reasons


def test_rejects_illiquid_instrument():
    instrument = make_instrument()
    candles = make_candles(instrument, 10, volume=Decimal("0.001"), price=Decimal("100"))
    snapshot = make_snapshot(instrument, Decimal("0.001"))
    evaluation = evaluate_instrument(instrument, candles, snapshot, CONFIG)
    assert not evaluation.eligible
    assert "illiquid" in evaluation.reasons


def test_rejects_wide_spread():
    instrument = make_instrument()
    candles = make_candles(instrument, 10, volume=Decimal("100"), price=Decimal("100"))
    snapshot = make_snapshot(instrument, Decimal("0.05"))
    evaluation = evaluate_instrument(instrument, candles, snapshot, CONFIG)
    assert not evaluation.eligible
    assert "wide_spread" in evaluation.reasons


def test_rejects_unavailable_snapshot():
    instrument = make_instrument()
    candles = make_candles(instrument, 10, volume=Decimal("100"), price=Decimal("100"))
    evaluation = evaluate_instrument(instrument, candles, None, CONFIG)
    assert not evaluation.eligible
    assert "unavailable" in evaluation.reasons


def test_evaluate_universe_and_eligible_instruments_filter_correctly():
    good = make_instrument(base="BTC")
    bad = make_instrument(base="ETH")
    good_candles = make_candles(good, 10, volume=Decimal("100"), price=Decimal("100"))
    bad_candles = make_candles(bad, 2, volume=Decimal("100"), price=Decimal("100"))
    snapshots = {
        good.id: make_snapshot(good, Decimal("0.001")),
        bad.id: make_snapshot(bad, Decimal("0.001")),
    }
    evaluations = evaluate_universe(
        [good, bad],
        {good.id: good_candles, bad.id: bad_candles},
        snapshots,
        CONFIG,
    )
    assert eligible_instruments(evaluations) == [good]
