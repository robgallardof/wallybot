"""On-chain wallet activity: `WalletIntelligenceProvider`'s output type and port, per
ARCHITECTURE.md's "Multi-source intelligence and Smart Money" and its "On-chain monitoring"
list of normalized action types.

A `WalletActivityEvent` is a normalized observation, never an interpretation: `action` records
what happened (a swap, a transfer, adding liquidity, ...), not what it *means* for a strategy --
"do not interpret a large transfer by itself as BUY or SELL... generate a signal and allow
strategy intelligence to interpret it in context" applies here exactly as it does to whale
transfers. `amount` is always positive; direction lives entirely in `action`.

Pure domain: no framework imports, no HTTP client, no provider SDK.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.entity import Attribution
from wallybot.domain.validation import require_aware_datetime


class OnChainActionType(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    MINT = "MINT"
    BURN = "BURN"
    ADD_LIQUIDITY = "ADD_LIQUIDITY"
    REMOVE_LIQUIDITY = "REMOVE_LIQUIDITY"
    APPROVE = "APPROVE"
    STAKE = "STAKE"
    UNSTAKE = "UNSTAKE"
    BRIDGE = "BRIDGE"


@dataclass(frozen=True)
class WalletActivityEvent:
    wallet_id: str
    chain: str
    transaction_hash: str
    token: str
    action: OnChainActionType
    amount: Decimal
    value_usd: Decimal | None
    price: Decimal | None
    liquidity_usd: Decimal | None
    occurred_at: datetime
    attribution: Attribution

    def __post_init__(self) -> None:
        for field, value in (
            ("wallet_id", self.wallet_id),
            ("chain", self.chain),
            ("transaction_hash", self.transaction_hash),
            ("token", self.token),
        ):
            if not value:
                raise ValueError(f"{field} is required")
        if self.amount <= 0:
            raise ValueError("amount must be positive; direction belongs to action, not sign")
        for field, value in (
            ("value_usd", self.value_usd),
            ("price", self.price),
            ("liquidity_usd", self.liquidity_usd),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{field} cannot be negative when present")
        require_aware_datetime(self.occurred_at, "occurred_at")


class WalletIntelligenceProvider(Protocol):
    """Normalizes a vendor's wallet-labeling/activity API into Wally domain objects. Read-only
    intelligence -- never trading credentials, never a withdrawal-capable connection."""

    async def fetch_wallet_activity(
        self, chain: str, address: str, since: datetime
    ) -> list[WalletActivityEvent]: ...

    async def fetch_wallet_labels(self, chain: str, address: str) -> tuple[Attribution, ...]: ...
