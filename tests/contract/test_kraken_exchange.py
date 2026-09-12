"""Kraken adapter contract test, using real recorded API responses (captured 2026-09-12) as
fixtures -- no live network call. Per TESTING.md: "do not depend on... external exchange
availability for mandatory tests."
"""

from datetime import UTC, datetime, timedelta

from tests.contract.market_data_provider_suite import (
    FixedClock,
    assert_discovers_valid_instruments,
    assert_fetches_candles_respecting_since_and_limit,
    assert_fetches_valid_snapshot,
)
from wallybot.exchanges.kraken import KrakenExchange

# Real https://api.kraken.com/0/public/AssetPairs?pair=XBTUSD,ETHUSD response.
_ASSET_PAIRS = {
    "error": [],
    "result": {
        "XETHZUSD": {
            "altname": "ETHUSD",
            "wsname": "ETH/USD",
            "base": "XETH",
            "quote": "ZUSD",
            "lot_decimals": 8,
            "ordermin": "0.001",
            "tick_size": "0.01",
            "status": "online",
        },
        "XXBTZUSD": {
            "altname": "XBTUSD",
            "wsname": "XBT/USD",
            "base": "XXBT",
            "quote": "ZUSD",
            "lot_decimals": 8,
            "ordermin": "0.00005",
            "tick_size": "0.1",
            "status": "online",
        },
    },
}

# Real https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60&since=... response.
_OHLC = {
    "error": [],
    "result": {
        "XXBTZUSD": [
            # time, open, high, low, close, vwap, volume, count
            [1789236000, "77194.7", "77203.3", "77105.3", "77124.4", "77158.7", "37.10020178",
             2557],
            [1789239600, "77124.4", "77172.7", "77050.0", "77104.6", "77107.9", "17.87523302",
             2544],
            [1789243200, "77104.6", "77207.2", "77104.6", "77146.4", "77168.9", "8.46572206",
             1940],
            [1789246800, "77146.6", "77250.0", "77134.9", "77233.9", "77198.4", "16.42041161",
             2093],
            [1789250400, "77233.9", "77245.6", "77233.9", "77242.0", "77242.3", "0.03810438", 50],
        ],
        "last": 1789246800,
    },
}
_OHLC_FIRST_OPEN_TIME = datetime.fromtimestamp(1789236000, tz=UTC)

# Real https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD response.
_TICKER = {
    "error": [],
    "result": {
        "XETHZUSD": {"a": ["2523.49000", "1", "1.000"], "b": ["2523.48000", "3", "3.000"]},
        "XXBTZUSD": {"a": ["77242.00000", "1", "1.000"], "b": ["77241.90000", "1", "1.000"]},
    },
}


class FixtureKrakenTransport:
    """Replays real, previously captured Kraken responses -- no network access at test time."""

    async def get(self, path: str, params: dict[str, str]) -> dict:
        if path == "/0/public/AssetPairs":
            return _ASSET_PAIRS
        if path == "/0/public/OHLC":
            return _OHLC
        if path == "/0/public/Ticker":
            return _TICKER
        raise ValueError(f"unexpected Kraken path in fixture transport: {path}")


def make_provider() -> KrakenExchange:
    return KrakenExchange(
        clock=FixedClock(datetime(2026, 9, 12, tzinfo=UTC)),
        transport=FixtureKrakenTransport(),
    )


async def test_discovers_valid_instruments() -> None:
    await assert_discovers_valid_instruments(make_provider())


async def test_fetches_candles_respecting_since_and_limit() -> None:
    await assert_fetches_candles_respecting_since_and_limit(
        make_provider(), "1h", _OHLC_FIRST_OPEN_TIME, limit=3
    )


async def test_fetches_valid_snapshot() -> None:
    await assert_fetches_valid_snapshot(make_provider())


async def test_rejects_unsupported_timeframe() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    try:
        await provider.fetch_candles(instrument, "3m", _OHLC_FIRST_OPEN_TIME, 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unsupported timeframe")


async def test_instrument_base_round_trips_into_a_valid_kraken_pair() -> None:
    # Kraken's own codes (e.g. "XBT" for Bitcoin) are passed through unrenamed specifically so
    # base+quote reconstructs a pair Kraken itself recognizes -- verified against the real
    # altname each fixture pair was recorded under.
    instruments = await make_provider().discover_instruments()
    altnames = {info["altname"] for info in _ASSET_PAIRS["result"].values()}
    for instrument in instruments:
        assert f"{instrument.base}{instrument.quote}" in altnames


async def test_limit_truncates_available_rows() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    candles = await provider.fetch_candles(instrument, "1h", _OHLC_FIRST_OPEN_TIME, limit=2)
    assert len(candles) == 2


async def test_candle_data_matches_the_recorded_response() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    candles = await provider.fetch_candles(instrument, "1h", _OHLC_FIRST_OPEN_TIME, limit=5)
    assert len(candles) == 5
    assert candles[0].open_time == _OHLC_FIRST_OPEN_TIME
    assert candles[0].close_time == _OHLC_FIRST_OPEN_TIME + timedelta(hours=1)
    assert str(candles[0].close) == "77124.4"
    assert candles[0].source == "kraken"
