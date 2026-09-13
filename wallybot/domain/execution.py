"""ExchangeGateway port and the value types it exchanges, per ARCHITECTURE.md's Contracts table
("Capabilities, balances, order lookup/submission/cancellation and fills; no withdrawal method")
and ADR-004 ("Expose no withdrawal function").

Lookups are keyed by `client_order_id`, not a venue-assigned ID -- DATA.md: "Client order IDs are
deterministic within venue restrictions and mapped durably before submission." This is what makes
UNKNOWN resolvable at all: `submit_order` can return UNKNOWN with no venue order ID (the response
was lost, not necessarily the order), and a later `lookup_order` can still find it because the
caller always knows its own client_order_id, matching ADR-008's reconcile-before-retry and
`docs/diagrams/order-lifecycle.md`'s "UNKNOWN --> ACKNOWLEDGED: Lookup resolves".

Pure domain: no framework imports, no network, no persistence. A concrete adapter (FakeExchange
for PAPER; a real venue adapter later, if LIVE is ever authorized) implements this Protocol
structurally.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.market import Instrument
from wallybot.domain.order import OrderIntent, Side


class SubmissionOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SubmissionResult:
    outcome: SubmissionOutcome
    venue_order_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is SubmissionOutcome.ACCEPTED and not self.venue_order_id:
            raise ValueError("an ACCEPTED submission must carry a venue_order_id")
        if self.outcome is SubmissionOutcome.REJECTED and not self.reason:
            raise ValueError("a REJECTED submission must carry a reason")


class VenueOrderStatus(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class OrderLookup:
    status: VenueOrderStatus
    cumulative_filled_quantity: Decimal
    average_fill_price: Decimal | None
    venue_order_id: str | None = None

    def __post_init__(self) -> None:
        if self.cumulative_filled_quantity < 0:
            raise ValueError("cumulative_filled_quantity cannot be negative")
        if self.average_fill_price is not None and self.average_fill_price <= 0:
            raise ValueError("average_fill_price must be positive when present")


class CancelOutcome(StrEnum):
    CANCELLED = "CANCELLED"
    FILL_WON_RACE = "FILL_WON_RACE"
    REJECTED_ZERO_FILLS = "REJECTED_ZERO_FILLS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CancelResult:
    outcome: CancelOutcome
    cumulative_filled_quantity: Decimal

    def __post_init__(self) -> None:
        if self.cumulative_filled_quantity < 0:
            raise ValueError("cumulative_filled_quantity cannot be negative")


@dataclass(frozen=True)
class Fill:
    fill_id: str
    client_order_id: str
    instrument: Instrument
    side: Side
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    filled_at: datetime

    def __post_init__(self) -> None:
        if not self.fill_id:
            raise ValueError("fill_id is required")
        if not self.client_order_id:
            raise ValueError("client_order_id is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.price <= 0:
            raise ValueError("price must be positive")
        if self.fee < 0:
            raise ValueError("fee cannot be negative")
        if not self.fee_currency:
            raise ValueError("fee_currency is required")


class ExchangeGateway(Protocol):
    """Capability an execution service submits paper (and, eventually, live) orders through.

    No withdrawal method exists anywhere on this Protocol -- not "guarded", simply absent,
    per ADR-004.
    """

    async def submit_order(self, intent: OrderIntent) -> SubmissionResult: ...
    async def cancel_order(self, client_order_id: str) -> CancelResult: ...
    async def lookup_order(self, client_order_id: str) -> OrderLookup: ...
    async def list_fills(self, client_order_id: str) -> tuple[Fill, ...]: ...
