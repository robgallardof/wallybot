"""Wallet Registry value types, per ARCHITECTURE.md's "Multi-source intelligence and Smart
Money". A wallet is administered, never auto-escalated: `monitoring_mode` defaults to `OBSERVE`
for every newly tracked wallet, matching ARCHITECTURE.md's "every newly created strategy or
newly tracked wallet/entity defaults to OBSERVE" -- nothing here ever mirrors a trade
automatically. `MonitoringMode.MIRROR` exists as a named state a future execution layer could
read, but no code in this codebase currently acts on it; enabling real trade mirroring is a
distinct, much later capability, not something flipping this enum value alone can do.

Performance fields the wider spec names (historical PnL, win rate, average hold time, trade
count, portfolio value, SmartMoneyScore) are deliberately NOT modeled as mutable fields on
`Wallet` here -- ARCHITECTURE.md's Smart Money Engine section says "store the score history,
never overwrite previous score snapshots," which means those belong to their own append-only
snapshot record (Phase 11), not fields that get overwritten in place on the registry entry.

Pure domain: no framework imports, no persistence, no provider I/O.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.entity import Attribution
from wallybot.domain.validation import require_aware_datetime, require_unit_interval


class MonitoringMode(StrEnum):
    OBSERVE = "OBSERVE"
    AI_EVALUATED = "AI_EVALUATED"
    MIRROR = "MIRROR"


@dataclass(frozen=True)
class Wallet:
    address: str
    chain: str
    entity_id: str | None
    alias: str | None
    labels: tuple[str, ...]
    tags: tuple[str, ...]
    confidence: Decimal
    trust_score: Decimal
    risk_score: Decimal
    enabled: bool
    influence_weight: Decimal
    max_signal_weight: Decimal
    max_allocation: Decimal | None
    min_transaction_value: Decimal
    attributions: tuple[Attribution, ...]
    created_at: datetime
    updated_at: datetime
    monitoring_mode: MonitoringMode = MonitoringMode.OBSERVE

    def __post_init__(self) -> None:
        if not self.address:
            raise ValueError("address is required")
        if not self.chain:
            raise ValueError("chain is required")
        for field, value in (
            ("confidence", self.confidence),
            ("trust_score", self.trust_score),
            ("risk_score", self.risk_score),
            ("influence_weight", self.influence_weight),
            ("max_signal_weight", self.max_signal_weight),
        ):
            require_unit_interval(value, field)
        if self.max_allocation is not None and self.max_allocation <= 0:
            raise ValueError("max_allocation must be positive when set")
        if self.min_transaction_value < 0:
            raise ValueError("min_transaction_value must be nonnegative")
        if not self.attributions:
            raise ValueError("a wallet needs at least one attribution -- provenance is mandatory")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")

    @property
    def id(self) -> str:
        return f"{self.chain}:{self.address}"


@dataclass(frozen=True)
class WalletCluster:
    """Independent wallets an operator or clustering heuristic has linked together -- e.g. one
    entity's several known addresses. Two or more wallets are required; a single wallet is not a
    cluster."""

    id: str
    entity_id: str | None
    wallet_ids: tuple[str, ...]
    confidence: Decimal
    evidence: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if len(self.wallet_ids) < 2:
            raise ValueError("a cluster needs at least two wallets")
        if len(set(self.wallet_ids)) != len(self.wallet_ids):
            raise ValueError("wallet_ids must be unique")
        if not self.evidence:
            raise ValueError("evidence is required")
        require_unit_interval(self.confidence, "confidence")
        require_aware_datetime(self.created_at, "created_at")
