"""Entity Correlation Graph value types, per ARCHITECTURE.md's "Multi-source intelligence and
Smart Money": typed relationships between wallets, entities, tokens, events and transactions,
each with its own provenance.

"The existing relational schema models this initially, a graph database is a later option if
query patterns actually need one" -- `Relationship` is deliberately a flat, generic edge (a typed
`source`/`target` pair, each a `NodeReference`) rather than a family of foreign-key columns per
node kind, so it stores cleanly in one relational table today and translates directly to a graph
edge later without a data model change, only a different query engine.

A `Relationship` is one claim, not an evolving record: if two independent sources report the same
real-world relationship, that is two `Relationship` rows (each with its own `Attribution`), not
one row with multiple attributions -- unlike `Entity`/`Wallet`, which accumulate corroborating
evidence about the same identity over time.

Pure domain: no framework imports, no persistence.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from wallybot.domain.entity import Attribution
from wallybot.domain.validation import require_aware_datetime


class NodeReferenceType(StrEnum):
    WALLET = "WALLET"
    ENTITY = "ENTITY"
    # Public graph-node kind, not an authentication token.
    TOKEN = "TOKEN"  # nosec B105
    EVENT = "EVENT"
    TRANSACTION = "TRANSACTION"


class RelationshipType(StrEnum):
    OWNS = "OWNS"
    CONTROLS = "CONTROLS"
    FUNDS = "FUNDS"
    TRADED = "TRADED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    TRANSFERRED_FROM = "TRANSFERRED_FROM"
    DEPLOYED = "DEPLOYED"
    HOLDS = "HOLDS"
    INVESTED_IN = "INVESTED_IN"
    RELATED_TO = "RELATED_TO"
    DISCLOSED_TRADE = "DISCLOSED_TRADE"
    INSIDER_OF = "INSIDER_OF"


@dataclass(frozen=True)
class NodeReference:
    """One endpoint of a `Relationship`. `Company`/`Person`/`Fund`/`Exchange` (named in the wider
    spec as separate node kinds) are all represented as `ENTITY` -- `Entity.entity_type` already
    distinguishes them; a relationship endpoint does not need to repeat that distinction."""

    node_type: NodeReferenceType
    node_id: str

    def __post_init__(self) -> None:
        if not self.node_id:
            raise ValueError("node_id is required")


@dataclass(frozen=True)
class Relationship:
    id: str
    source: NodeReference
    relationship_type: RelationshipType
    target: NodeReference
    attribution: Attribution
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("id is required")
        if self.source == self.target:
            raise ValueError("a relationship cannot link a node to itself")
        require_aware_datetime(self.created_at, "created_at")
