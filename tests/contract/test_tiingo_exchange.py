"""Tiingo adapter contract test, using fixture responses shaped per Tiingo's documented crypto
API contract -- no live network call, and no real API key needed. Per TESTING.md: "do not depend
on... external exchange availability for mandatory tests." Unlike test_kraken_exchange.py's
recorded-real-response fixtures, these are shaped from documentation (a real key wasn't available
at the time this adapter was written) -- if Tiingo's actual response ever disagrees with this
shape, that is the adapter bug to go find, not a reason to loosen these fixtures.
"""

from datetime import UTC, datetime, timedelta

import pytest

from tests.contract.market_data_provider_suite import (
    FixedClock,
    assert_discovers_valid_instruments,
    assert_fetches_candles_respecting_since_and_limit,
)
from wallybot.exchanges.tiingo import TiingoExchange

# Shaped per https://www.tiingo.com/documentation/crypto's documented /tiingo/crypto response.
_CRYPTO_METADATA = [
    {"ticker": "btcusd", "baseCurrency": "btc", "quoteCurrency": "usd", "name": "Bitcoin/USD"},
    {"ticker": "ethusd", "baseCurrency": "eth", "quoteCurrency": "usd", "name": "Ethereum/USD"},
]

# Shaped per https://www.tiingo.com/documentation/crypto's documented /tiingo/crypto/prices
# response: a list with one entry per requested ticker, each holding a priceData array.
_PRICES = [
    {
        "ticker": "btcusd",
        "baseCurrency": "btc",
        "quoteCurrency": "usd",
        "priceData": [
            {
                "date": "2026-09-12T20:00:00.000Z",
                "open": 77194.7,
                "high": 77203.3,
                "low": 77105.3,
                "close": 77124.4,
                "volume": 37.1002,
                "volumeNotional": 2861234.5,
                "tradesDone": 2557,
            },
            {
                "date": "2026-09-12T21:00:00.000Z",
                "open": 77124.4,
                "high": 77172.7,
                "low": 77050.0,
                "close": 77104.6,
                "volume": 17.875,
                "volumeNotional": 1378234.1,
                "tradesDone": 2544,
            },
            {
                "date": "2026-09-12T22:00:00.000Z",
                "open": 77104.6,
                "high": 77207.2,
                "low": 77104.6,
                "close": 77146.4,
                "volume": 8.4657,
                "volumeNotional": 653012.9,
                "tradesDone": 1940,
            },
        ],
    }
]
_PRICES_FIRST_OPEN_TIME = datetime(2026, 9, 12, 20, tzinfo=UTC)


class FixtureTiingoTransport:
    """Replays documented-shape Tiingo responses -- no network access at test time."""

    async def get(self, path: str, params: dict[str, str]):
        if path == "/tiingo/crypto":
            return _CRYPTO_METADATA
        if path == "/tiingo/crypto/prices":
            return _PRICES
        raise ValueError(f"unexpected Tiingo path in fixture transport: {path}")


def make_provider() -> TiingoExchange:
    # After the fixture's last row (22:00-open, closing 23:00) so every fixture candle is closed.
    return TiingoExchange(
        clock=FixedClock(datetime(2026, 9, 12, 23, 5, tzinfo=UTC)),
        transport=FixtureTiingoTransport(),
    )


async def test_discovers_valid_instruments() -> None:
    await assert_discovers_valid_instruments(make_provider())


async def test_discovered_instruments_have_no_reported_precision() -> None:
    # The one real, verified gap in Tiingo's crypto metadata -- never fabricated, always None.
    instruments = await make_provider().discover_instruments()
    for instrument in instruments:
        assert instrument.price_increment is None
        assert instrument.quantity_increment is None
        assert instrument.min_quantity is None


async def test_fetches_candles_respecting_since_and_limit() -> None:
    await assert_fetches_candles_respecting_since_and_limit(
        make_provider(), "1h", _PRICES_FIRST_OPEN_TIME, limit=2
    )


async def test_rejects_unsupported_timeframe() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        await provider.fetch_candles(instrument, "1d", _PRICES_FIRST_OPEN_TIME, 1)


async def test_limit_truncates_available_rows() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    candles = await provider.fetch_candles(instrument, "1h", _PRICES_FIRST_OPEN_TIME, limit=2)
    assert len(candles) == 2


async def test_candle_data_matches_the_fixture_response() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    candles = await provider.fetch_candles(instrument, "1h", _PRICES_FIRST_OPEN_TIME, limit=5)
    assert len(candles) == 3
    assert candles[0].open_time == _PRICES_FIRST_OPEN_TIME
    assert candles[0].close_time == _PRICES_FIRST_OPEN_TIME + timedelta(hours=1)
    assert str(candles[0].close) == "77124.4"
    assert candles[0].source == "tiingo"


async def test_fetch_snapshot_is_not_available() -> None:
    # Tiingo's crypto top-of-book endpoint is deprecated with no documented replacement -- this
    # adapter is honest about that rather than fabricating a bid/ask.
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    with pytest.raises(NotImplementedError):
        await provider.fetch_snapshot(instrument)


async def test_ticker_concatenates_base_and_quote_lowercase() -> None:
    instruments = await make_provider().discover_instruments()
    tickers = {entry["ticker"] for entry in _CRYPTO_METADATA}
    for instrument in instruments:
        assert f"{instrument.base}{instrument.quote}".lower() in tickers
