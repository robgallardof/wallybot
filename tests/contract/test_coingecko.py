"""CoinGecko adapter contract test, using a real recorded API response (captured 2026-09-13) as
a fixture -- no live network call. Per TESTING.md: "do not depend on... external exchange
availability for mandatory tests."
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.market.coingecko import CoinGeckoMarketMetadataProvider

# Real https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum
# response (trimmed to the fields this adapter reads).
_MARKETS = [
    {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "market_cap": 1550502144718,
        "fully_diluted_valuation": 1550506236454,
        "total_volume": 15292184429,
        "circulating_supply": 20083556.0,
        "total_supply": 20083609.0,
        "max_supply": 21000000.0,
        "last_updated": "2026-09-13T04:30:20.000Z",
    },
    {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "market_cap": 307828830878,
        "fully_diluted_valuation": 307828830878,
        "total_volume": 7788006855,
        "circulating_supply": 122044301.968694,
        "total_supply": 122044301.968694,
        "max_supply": None,
        "last_updated": "2026-09-13T04:30:20.000Z",
    },
]


class FixtureCoinGeckoTransport:
    """Replays a real, previously captured CoinGecko response -- no network access at test time."""

    async def get(self, path: str, params: dict[str, str]) -> list[dict]:
        if path == "/api/v3/coins/markets":
            return _MARKETS
        raise ValueError(f"unexpected CoinGecko path in fixture transport: {path}")


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_provider() -> CoinGeckoMarketMetadataProvider:
    return CoinGeckoMarketMetadataProvider(
        clock=FixedClock(datetime(2026, 9, 13, tzinfo=UTC)), transport=FixtureCoinGeckoTransport()
    )


async def test_fetches_and_normalizes_real_recorded_market_data() -> None:
    results = await make_provider().fetch_token_metadata(["bitcoin", "ethereum"])
    assert len(results) == 2

    bitcoin = next(r for r in results if r.token_id == "bitcoin")
    assert bitcoin.symbol == "btc"
    assert bitcoin.name == "Bitcoin"
    assert bitcoin.market_cap_usd == Decimal("1550502144718")
    assert bitcoin.max_supply == Decimal("21000000.0")
    assert bitcoin.source == "coingecko"
    assert bitcoin.source_updated_at == datetime(2026, 9, 13, 4, 30, 20, tzinfo=UTC)


async def test_a_token_with_no_hard_cap_reports_max_supply_as_none_not_zero() -> None:
    results = await make_provider().fetch_token_metadata(["bitcoin", "ethereum"])
    ethereum = next(r for r in results if r.token_id == "ethereum")
    assert ethereum.max_supply is None


async def test_rejects_an_empty_token_id_list() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await make_provider().fetch_token_metadata([])
