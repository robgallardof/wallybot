"""CoinGecko adapter using its public (unauthenticated) `/coins/markets` REST endpoint.

Public endpoint only -- no API key required, verified live: `curl
"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=bitcoin,ethereum"` returns
real market metadata with no auth header. Matches this port's own "never trading credentials"
rule the same way `wallybot/exchanges/kraken.py`'s public endpoints do.

CoinGecko's JSON numbers decode as Python `int`/`float`; every numeric field is converted via
`Decimal(str(value))`, never `Decimal(value)` directly on a float, to avoid binary
floating-point artifacts leaking into a value this codebase treats as authoritative money/supply
data (ARCHITECTURE.md's Contracts: "monetary values use decimal types").
"""

from datetime import datetime
from decimal import Decimal
from typing import Protocol

import httpx

from wallybot.domain.clock import Clock
from wallybot.domain.market_metadata import TokenMarketMetadata

_BASE_URL = "https://api.coingecko.com"


class CoinGeckoTransport(Protocol):
    """The narrow HTTP surface CoinGeckoMarketMetadataProvider needs -- swappable for a fixture
    in tests, per TESTING.md: mandatory tests must not depend on external provider availability.
    """

    async def get(self, path: str, params: dict[str, str]) -> list[dict]: ...


class HttpxCoinGeckoTransport:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0)

    async def get(self, path: str, params: dict[str, str]) -> list[dict]:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()


def _decimal_or_none(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


class CoinGeckoMarketMetadataProvider:
    """Implements wallybot.domain.market_metadata.MarketMetadataProvider (structural, not
    inherited)."""

    def __init__(self, clock: Clock, transport: CoinGeckoTransport | None = None) -> None:
        self.clock = clock
        self.transport = transport or HttpxCoinGeckoTransport()

    async def fetch_token_metadata(self, token_ids: list[str]) -> list[TokenMarketMetadata]:
        if not token_ids:
            raise ValueError("token_ids must not be empty")
        payload = await self.transport.get(
            "/api/v3/coins/markets", {"vs_currency": "usd", "ids": ",".join(token_ids)}
        )
        now = self.clock.now()
        return [
            TokenMarketMetadata(
                token_id=row["id"],
                symbol=row["symbol"],
                name=row["name"],
                market_cap_usd=_decimal_or_none(row.get("market_cap")),
                fully_diluted_valuation_usd=_decimal_or_none(row.get("fully_diluted_valuation")),
                volume_24h_usd=_decimal_or_none(row.get("total_volume")),
                circulating_supply=_decimal_or_none(row.get("circulating_supply")),
                total_supply=_decimal_or_none(row.get("total_supply")),
                max_supply=_decimal_or_none(row.get("max_supply")),
                source="coingecko",
                source_updated_at=datetime.fromisoformat(row["last_updated"]),
                fetched_at=now,
            )
            for row in payload
        ]
