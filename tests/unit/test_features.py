from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.features import LookaheadError
from wallybot.domain.market import Candle, Instrument, MarketType
from wallybot.features.simple import SimpleFeatureEngine

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


def make_candle(open_time: datetime, close: Decimal) -> Candle:
    return Candle(
        instrument=INSTRUMENT,
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=Decimal("1"),
        source="fake",
        received_at=open_time + timedelta(hours=1, seconds=1),
    )


def make_series(closes: list[str]) -> list[Candle]:
    return [
        make_candle(START + timedelta(hours=i), Decimal(value))
        for i, value in enumerate(closes)
    ]


def test_computes_sma_and_momentum():
    candles = make_series(["100", "110", "120", "130"])
    as_of = candles[-1].close_time
    engine = SimpleFeatureEngine()
    vector = engine.compute(candles, as_of=as_of, window=4)
    assert vector.values["sma_4"] == Decimal("115")
    assert vector.values["momentum_4"] == Decimal("0.3")
    assert vector.version == 1
    assert vector.instrument == INSTRUMENT
    assert vector.timeframe == "1h"


def test_uses_only_the_trailing_window():
    candles = make_series(["1000", "100", "110", "120", "130"])
    as_of = candles[-1].close_time
    vector = SimpleFeatureEngine().compute(candles, as_of=as_of, window=4)
    assert vector.values["sma_4"] == Decimal("115")


def test_rejects_future_candle_beyond_as_of():
    candles = make_series(["100", "110", "120", "130"])
    as_of = candles[-2].close_time  # earlier than the last candle's close
    with pytest.raises(LookaheadError):
        SimpleFeatureEngine().compute(candles, as_of=as_of, window=4)


def test_rejects_insufficient_history():
    candles = make_series(["100", "110"])
    as_of = candles[-1].close_time
    with pytest.raises(ValueError):
        SimpleFeatureEngine().compute(candles, as_of=as_of, window=4)


def test_rejects_empty_candles():
    with pytest.raises(ValueError):
        SimpleFeatureEngine().compute([], as_of=START, window=4)


def test_rejects_nonpositive_window():
    candles = make_series(["100", "110"])
    with pytest.raises(ValueError):
        SimpleFeatureEngine().compute(candles, as_of=candles[-1].close_time, window=0)


def test_rejects_mixed_instruments():
    other = Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base="ETH",
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
    )
    mismatched = Candle(
        instrument=other,
        timeframe="1h",
        open_time=START + timedelta(hours=1),
        close_time=START + timedelta(hours=2),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1"),
        source="fake",
        received_at=START + timedelta(hours=2, seconds=1),
    )
    candles = [make_candle(START, Decimal("100")), mismatched]
    with pytest.raises(ValueError):
        SimpleFeatureEngine().compute(candles, as_of=candles[-1].close_time, window=2)
