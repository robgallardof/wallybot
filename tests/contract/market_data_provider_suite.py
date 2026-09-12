"""Shared contract suite: any MarketDataProvider (Fake, Kraken, later adapters) must satisfy this.

Import these functions from a per-adapter test module (see test_fake_exchange.py) rather than
parametrizing here, so each adapter's test failures are attributed to that adapter.
"""

from datetime import datetime

from wallybot.domain.market import MarketDataProvider


async def assert_discovers_valid_instruments(provider: MarketDataProvider) -> None:
    instruments = await provider.discover_instruments()
    assert instruments, "provider must discover at least one instrument"
    for instrument in instruments:
        assert instrument.venue
        assert instrument.base and instrument.quote
        assert instrument.price_increment > 0
        assert instrument.quantity_increment > 0
        pair = f"{instrument.base}/{instrument.quote}"
        expected_id = f"{instrument.venue}:{instrument.market_type}:{pair}"
        assert instrument.id == expected_id


async def assert_fetches_candles_respecting_since_and_limit(
    provider: MarketDataProvider, timeframe: str, since: datetime, limit: int
) -> None:
    instruments = await provider.discover_instruments()
    instrument = instruments[0]
    candles = await provider.fetch_candles(instrument, timeframe, since, limit)
    assert len(candles) <= limit
    for candle in candles:
        assert candle.instrument == instrument
        assert candle.timeframe == timeframe
        assert candle.open_time >= since
    for earlier, later in zip(candles, candles[1:], strict=False):
        assert later.open_time >= earlier.close_time, "candles must not overlap or go backwards"
