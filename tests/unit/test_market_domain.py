from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.market import Candle, Instrument, MarketType


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


def make_candle(**overrides) -> Candle:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    fields = {
        "instrument": make_instrument(),
        "timeframe": "1h",
        "open_time": now - timedelta(hours=1),
        "close_time": now,
        "open": Decimal("100"),
        "high": Decimal("110"),
        "low": Decimal("90"),
        "close": Decimal("105"),
        "volume": Decimal("1.5"),
        "source": "fake",
        "received_at": now,
    }
    fields.update(overrides)
    return Candle(**fields)


def test_instrument_id_includes_venue_market_type_and_pair():
    instrument = make_instrument()
    assert instrument.id == "fake:SPOT:BTC/USD"


def test_instrument_rejects_nonpositive_increments():
    with pytest.raises(ValueError):
        make_instrument(price_increment=Decimal("0"))


def test_candle_accepts_valid_values():
    candle = make_candle()
    assert candle.close == Decimal("105")


def test_candle_rejects_naive_datetime():
    with pytest.raises(ValueError):
        make_candle(open_time=datetime(2026, 1, 1))


def test_candle_rejects_close_time_before_open_time():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        make_candle(open_time=now, close_time=now - timedelta(hours=1))


def test_candle_rejects_low_above_open_or_close():
    with pytest.raises(ValueError):
        make_candle(low=Decimal("101"))


def test_candle_rejects_high_below_open_or_close():
    with pytest.raises(ValueError):
        make_candle(high=Decimal("101"))


def test_candle_rejects_nonpositive_price():
    with pytest.raises(ValueError):
        make_candle(open=Decimal("0"))


def test_candle_rejects_negative_volume():
    with pytest.raises(ValueError):
        make_candle(volume=Decimal("-1"))
