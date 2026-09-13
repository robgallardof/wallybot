"""Shared contract suite: any ExchangeGateway (FakeExchange today; a real venue execution adapter,
if LIVE is ever authorized, later) must satisfy this. Mirrors market_data_provider_suite.py's
pattern -- import these functions from a per-adapter test module rather than parametrizing here,
so each adapter's failures are attributed to that adapter.

Covers exactly Phase 4 Slice 2's acceptance evidence (docs/PHASE_4.md): submit-then-lookup
round-trips, cancel races, accept-then-timeout.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from wallybot.domain.execution import (
    CancelOutcome,
    ExchangeGateway,
    SubmissionOutcome,
    VenueOrderStatus,
)
from wallybot.domain.market import Instrument
from wallybot.domain.order import OrderIntent, OrderKind, Side

MakeIntent = Callable[..., OrderIntent]


def intent_factory(instrument: Instrument, now: datetime) -> MakeIntent:
    """Returns a `make_intent(client_order_id, **overrides)` bound to one instrument/clock, so
    contract tests only ever have to name what differs from a plausible default order."""

    def make(client_order_id: str, **overrides: Any) -> OrderIntent:
        fields: dict[str, Any] = {
            "account_id": "acct-1",
            "environment": "PAPER",
            "instrument": instrument,
            "side": Side.BUY,
            "kind": OrderKind.MARKET,
            "quantity": instrument.min_quantity * 10,
            "limit_price": None,
            "decision_id": "decision-1",
            "client_order_id": client_order_id,
            "idempotency_key": client_order_id,
            "risk_assessment_id": "risk-1",
            "config_versions": {},
            "created_at": now,
            "expires_at": now + timedelta(hours=1),
        }
        fields.update(overrides)
        return OrderIntent(**fields)

    return make


async def assert_submit_then_lookup_round_trips(
    gateway: ExchangeGateway, make_intent: MakeIntent
) -> None:
    intent = make_intent("order-round-trip")
    result = await gateway.submit_order(intent)
    assert result.outcome is SubmissionOutcome.ACCEPTED
    assert result.venue_order_id

    lookup = await gateway.lookup_order(intent.client_order_id)
    assert lookup.status in (
        VenueOrderStatus.ACKNOWLEDGED,
        VenueOrderStatus.PARTIALLY_FILLED,
        VenueOrderStatus.FILLED,
    )
    assert lookup.venue_order_id == result.venue_order_id

    fills = await gateway.list_fills(intent.client_order_id)
    total_filled = sum((fill.quantity for fill in fills), Decimal(0))
    assert total_filled == lookup.cumulative_filled_quantity


async def assert_accept_then_timeout_resolves_via_lookup(
    gateway: ExchangeGateway, make_intent: MakeIntent
) -> None:
    intent = make_intent("order-timeout")
    result = await gateway.submit_order(intent)
    # The caller's own submission response is ambiguous...
    assert result.outcome is SubmissionOutcome.UNKNOWN
    assert result.venue_order_id is None
    # ...but the order was genuinely accepted at the venue, and a lookup by the client_order_id
    # the caller always controlled -- never the lost venue_order_id -- still resolves it. This is
    # ADR-008's reconcile-before-retry: no blind resubmission is ever required or safe here.
    lookup = await gateway.lookup_order(intent.client_order_id)
    assert lookup.status is not VenueOrderStatus.NOT_FOUND


async def assert_cancel_wins_when_no_fill_posted(
    gateway: ExchangeGateway, make_intent: MakeIntent
) -> None:
    intent = make_intent("order-cancel-clean", kind=OrderKind.LIMIT, limit_price=Decimal("1"))
    await gateway.submit_order(intent)
    cancel = await gateway.cancel_order(intent.client_order_id)
    assert cancel.outcome is CancelOutcome.CANCELLED
    assert cancel.cumulative_filled_quantity == 0
    lookup = await gateway.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.CANCELLED


async def assert_cancel_loses_race_to_a_completed_fill(
    gateway: ExchangeGateway, make_intent: MakeIntent
) -> None:
    # An unscripted MARKET order fills immediately and fully -- by the time cancel_order runs,
    # the fill has already won.
    intent = make_intent("order-cancel-race")
    await gateway.submit_order(intent)
    cancel = await gateway.cancel_order(intent.client_order_id)
    assert cancel.outcome is CancelOutcome.FILL_WON_RACE
    assert cancel.cumulative_filled_quantity == intent.quantity
