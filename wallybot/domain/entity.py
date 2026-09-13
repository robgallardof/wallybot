"""Entity Registry value types, per ARCHITECTURE.md's "Multi-source intelligence and Smart
Money": real-world actors (person, fund, exchange, whale, protocol, ...) tracked with confidence/
trust/risk/influence scores and full source provenance.

"Never assume an external attribution is absolute truth" is enforced structurally, not just by
convention: an `Entity` cannot be constructed without at least one `Attribution`, and an
`Attribution` always carries its source, confidence, evidence and verification status. An entity
attributed by several independent sources (e.g. Arkham entity intelligence *and* a public
disclosure dataset) keeps every attribution -- there is deliberately no single flat `source`
field on `Entity` itself, because that would only be able to represent one source at a time.

Pure domain: no framework imports, no persistence, no provider I/O.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.validation import require_aware_datetime, require_unit_interval


class EntityType(StrEnum):
    PERSON = "PERSON"
    PUBLIC_FIGURE = "PUBLIC_FIGURE"
    POLITICIAN = "POLITICIAN"
    FUND = "FUND"
    COMPANY = "COMPANY"
    EXCHANGE = "EXCHANGE"
    INSTITUTION = "INSTITUTION"
    WHALE = "WHALE"
    TRADER = "TRADER"
    WALLET_CLUSTER = "WALLET_CLUSTER"
    ANONYMOUS_WALLET = "ANONYMOUS_WALLET"
    DEVELOPER = "DEVELOPER"
    MARKET_MAKER = "MARKET_MAKER"
    PROTOCOL = "PROTOCOL"
    ETF = "ETF"
    GOVERNMENT = "GOVERNMENT"
    CUSTOM = "CUSTOM"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    CORROBORATED = "CORROBORATED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"


@dataclass(frozen=True)
class Attribution:
    """One external or operator claim backing part of an `Entity`/`Wallet` record."""

    source: str
    source_entity_id: str | None
    confidence: Decimal
    evidence: str
    verification_status: VerificationStatus
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source is required")
        if not self.evidence:
            raise ValueError("evidence is required")
        require_unit_interval(self.confidence, "confidence")
        require_aware_datetime(self.observed_at, "observed_at")


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    entity_type: EntityType
    aliases: tuple[str, ...]
    description: str
    enabled: bool
    confidence: Decimal
    trust_score: Decimal
    risk_score: Decimal
    influence_weight: Decimal
    tags: tuple[str, ...]
    attributions: tuple[Attribution, ...]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if not self.name:
            raise ValueError("name is required")
        for field, value in (
            ("confidence", self.confidence),
            ("trust_score", self.trust_score),
            ("risk_score", self.risk_score),
            ("influence_weight", self.influence_weight),
        ):
            require_unit_interval(value, field)
        if not self.attributions:
            raise ValueError("an entity needs at least one attribution -- provenance is mandatory")
        require_aware_datetime(self.created_at, "created_at")
        require_aware_datetime(self.updated_at, "updated_at")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
