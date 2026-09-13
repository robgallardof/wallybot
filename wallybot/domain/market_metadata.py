"""MarketMetadataProvider port and its value type, per ARCHITECTURE.md's Contracts table:
"Return timestamped provenance and unknown/missing fields explicitly."

A field the provider did not return is `None`, never a fabricated zero or guessed value --
`max_supply` genuinely does not exist for some tokens (Ethereum has none), and that is a fact
about the token, not missing data to paper over. `source_updated_at` is the provider's own claim
about when its data was last refreshed; `fetched_at` is when *this* system retrieved it -- the
same "exchange time vs. received time" distinction `wallybot/domain/market.py`'s `Candle`
already makes, applied to metadata instead of price history.

Pure domain: no framework imports, no HTTP client, no provider SDK.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from wallybot.domain.validation import require_aware_datetime


@dataclass(frozen=True)
class TokenMarketMetadata:
    token_id: str
    symbol: str
    name: str
    market_cap_usd: Decimal | None
    fully_diluted_valuation_usd: Decimal | None
    volume_24h_usd: Decimal | None
    circulating_supply: Decimal | None
    total_supply: Decimal | None
    max_supply: Decimal | None
    source: str
    source_updated_at: datetime
    fetched_at: datetime

    def __post_init__(self) -> None:
        for field, value in (
            ("token_id", self.token_id),
            ("symbol", self.symbol),
            ("name", self.name),
            ("source", self.source),
        ):
            if not value:
                raise ValueError(f"{field} is required")
        for field, value in (
            ("market_cap_usd", self.market_cap_usd),
            ("fully_diluted_valuation_usd", self.fully_diluted_valuation_usd),
            ("volume_24h_usd", self.volume_24h_usd),
            ("circulating_supply", self.circulating_supply),
            ("total_supply", self.total_supply),
            ("max_supply", self.max_supply),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{field} cannot be negative when present")
        require_aware_datetime(self.source_updated_at, "source_updated_at")
        require_aware_datetime(self.fetched_at, "fetched_at")


class MarketMetadataProvider(Protocol):
    """Timestamped token metadata (market cap, FDV, volume, supply) -- never trading
    credentials, never a substitute for `MarketDataProvider`'s candles/snapshots."""

    async def fetch_token_metadata(self, token_ids: list[str]) -> list[TokenMarketMetadata]: ...
