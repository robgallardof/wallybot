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
        make_candle(START + timedelta(hours=i), Decimal(value)) for i, value in enumerate(closes)
    ]


def test_computes_sma_and_momentum():
    candles = make_series(["100", "110", "120", "130"])
    as_of = candles[-1].close_time
    engine = SimpleFeatureEngine()
    vector = engine.compute(candles, as_of=as_of, window=4)
    assert vector.values["sma_4"] == Decimal("115")
    assert vector.values["momentum_4"] == Decimal("0.3")
    assert vector.version == 2
    assert vector.instrument == INSTRUMENT
    assert vector.timeframe == "1h"


def test_uses_only_the_trailing_window():
    candles = make_series(["1000", "100", "110", "120", "130"])
    as_of = candles[-1].close_time
    vector = SimpleFeatureEngine().compute(candles, as_of=as_of, window=4)
    assert vector.values["sma_4"] == Decimal("115")


def test_computes_volatility_atr_and_volume_features_from_the_same_as_of_window():
    candles = [
        Candle(
            instrument=INSTRUMENT,
            timeframe="1h",
            open_time=START + timedelta(hours=index),
            close_time=START + timedelta(hours=index + 1),
            open=Decimal(open_),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            volume=Decimal(volume),
            source="fake",
            received_at=START + timedelta(hours=index + 1),
        )
        for index, (open_, high, low, close, volume) in enumerate(
            [
                ("100", "102", "99", "101", "10"),
                ("101", "105", "100", "104", "20"),
                ("104", "106", "102", "103", "30"),
            ]
        )
    ]
    vector = SimpleFeatureEngine().compute(candles, as_of=candles[-1].close_time, window=3)

    assert vector.values["atr_3"] == Decimal("4")
    assert vector.values["relative_volume_3"] == Decimal("1.5")
    assert vector.values["average_quote_volume_3"] == Decimal("2060")
    expected_volatility = (((Decimal(3) / 101) ** 2 + (Decimal(-1) / 104) ** 2) / 2).sqrt()
    assert vector.values["realized_volatility_3"] == expected_volatility


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
