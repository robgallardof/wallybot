"""OrderIntent and the OrderStatus state machine, per docs/diagrams/order-lifecycle.md and
ADR-008's "durable intent and reconcile-before-retry" decision.

Pure domain: no database, no exchange call, no execution. `transition_to` is the only way an
OrderIntent's status changes, and it enforces the diagram's edges exactly -- an illegal jump
(e.g. CREATED straight to FILLED) raises InvalidOrderTransition rather than silently succeeding.
"Ambiguity enters UNKNOWN, retains reservations and reconciles before retry" (ADR-008) is encoded
directly in _TRANSITIONS: UNKNOWN can only resolve to what a lookup could actually observe, or
back to VALIDATED for a proven-safe retry -- never straight to FILLED-without-lookup or similar.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from wallybot.domain.market import Instrument


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"


TERMINAL_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FAILED}
)

# Matches docs/diagrams/order-lifecycle.md's stateDiagram edges exactly -- do not add an edge
# here that isn't drawn there; the diagram is the spec, not a suggestion.
_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.VALIDATED, OrderStatus.REJECTED}),
    OrderStatus.VALIDATED: frozenset({OrderStatus.SUBMITTING, OrderStatus.REJECTED}),
    OrderStatus.SUBMITTING: frozenset(
        {OrderStatus.SUBMITTED, OrderStatus.UNKNOWN, OrderStatus.REJECTED, OrderStatus.FAILED}
    ),
    OrderStatus.SUBMITTED: frozenset({OrderStatus.ACKNOWLEDGED, OrderStatus.UNKNOWN}),
    OrderStatus.ACKNOWLEDGED: frozenset(
        {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_REQUESTED}
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_REQUESTED}
    ),
    OrderStatus.CANCEL_REQUESTED: frozenset(
        {
            OrderStatus.CANCELLED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.FILLED,
            OrderStatus.UNKNOWN,
        }
    ),
    OrderStatus.UNKNOWN: frozenset(
        {
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.VALIDATED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.FAILED: frozenset(),
}


class InvalidOrderTransition(ValueError):
    pass


def can_transition(current: OrderStatus, next_status: OrderStatus) -> bool:
    return next_status in _TRANSITIONS[current]


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderKind(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass(frozen=True)
class OrderIntent:
    account_id: str
    environment: Literal["PAPER", "LIVE"]
    instrument: Instrument
    side: Side
    kind: OrderKind
    quantity: Decimal
    limit_price: Decimal | None
    decision_id: str
    client_order_id: str
    idempotency_key: str
    risk_assessment_id: str
    config_versions: Mapping[str, int]
    created_at: datetime
    expires_at: datetime
    status: OrderStatus = OrderStatus.CREATED

    def __post_init__(self) -> None:
        if self.environment not in ("PAPER", "LIVE"):
            raise ValueError("environment must be PAPER or LIVE")
        for name, value in (
            ("account_id", self.account_id),
            ("decision_id", self.decision_id),
            ("client_order_id", self.client_order_id),
            ("idempotency_key", self.idempotency_key),
            ("risk_assessment_id", self.risk_assessment_id),
        ):
            if not value:
                raise ValueError(f"{name} is required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.kind == OrderKind.LIMIT and self.limit_price is None:
            raise ValueError("limit orders require a limit_price")
        if self.kind == OrderKind.MARKET and self.limit_price is not None:
            raise ValueError("market orders must not carry a limit_price")
        if self.limit_price is not None and self.limit_price <= 0:
            raise ValueError("limit_price must be positive")
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")

    def transition_to(self, next_status: OrderStatus) -> "OrderIntent":
        if not can_transition(self.status, next_status):
            raise InvalidOrderTransition(
                f"cannot transition from {self.status} to {next_status}"
            )
        return replace(self, status=next_status)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
