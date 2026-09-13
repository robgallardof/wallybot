from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import (
    InvalidOrderTransition,
    OrderIntent,
    OrderKind,
    OrderStatus,
    Side,
    can_transition,
)

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)
EXPIRES_AT = CREATED_AT + timedelta(minutes=5)


def make_intent(**overrides) -> OrderIntent:
    fields = {
        "account_id": "acct-1",
        "environment": "PAPER",
        "instrument": INSTRUMENT,
        "side": Side.BUY,
        "kind": OrderKind.MARKET,
        "quantity": Decimal("0.01"),
        "limit_price": None,
        "decision_id": "decision-1",
        "client_order_id": "client-1",
        "idempotency_key": "idem-1",
        "risk_assessment_id": "risk-1",
        "config_versions": {"risk_policy": 1, "portfolio_policy": 1},
        "created_at": CREATED_AT,
        "expires_at": EXPIRES_AT,
    }
    fields.update(overrides)
    return OrderIntent(**fields)


def test_accepts_valid_market_order():
    intent = make_intent()
    assert intent.status == OrderStatus.CREATED
    assert intent.is_terminal is False


def test_rejects_invalid_environment():
    with pytest.raises(ValueError):
        make_intent(environment="TESTNET")


def test_rejects_nonpositive_quantity():
    with pytest.raises(ValueError):
        make_intent(quantity=Decimal("0"))


def test_market_order_must_not_carry_limit_price():
    with pytest.raises(ValueError):
        make_intent(kind=OrderKind.MARKET, limit_price=Decimal("100"))


def test_limit_order_requires_limit_price():
    with pytest.raises(ValueError):
        make_intent(kind=OrderKind.LIMIT, limit_price=None)


def test_limit_order_with_price_is_valid():
    intent = make_intent(kind=OrderKind.LIMIT, limit_price=Decimal("100"))
    assert intent.limit_price == Decimal("100")


def test_rejects_nonpositive_limit_price():
    with pytest.raises(ValueError):
        make_intent(kind=OrderKind.LIMIT, limit_price=Decimal("0"))


def test_rejects_missing_required_identifiers():
    required_fields = (
        "account_id",
        "decision_id",
        "client_order_id",
        "idempotency_key",
        "risk_assessment_id",
    )
    for field in required_fields:
        with pytest.raises(ValueError):
            make_intent(**{field: ""})


def test_rejects_expiry_not_after_created_at():
    with pytest.raises(ValueError):
        make_intent(expires_at=CREATED_AT)


def test_full_happy_path_transition_sequence():
    intent = make_intent()
    for status in (
        OrderStatus.VALIDATED,
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.ACKNOWLEDGED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
    ):
        intent = intent.transition_to(status)
    assert intent.status == OrderStatus.FILLED
    assert intent.is_terminal is True


def test_rejects_illegal_jump_from_created_to_filled():
    intent = make_intent()
    with pytest.raises(InvalidOrderTransition):
        intent.transition_to(OrderStatus.FILLED)


def test_unknown_can_resolve_back_to_validated_for_safe_retry():
    intent = make_intent()
    intent = intent.transition_to(OrderStatus.VALIDATED).transition_to(OrderStatus.SUBMITTING)
    intent = intent.transition_to(OrderStatus.UNKNOWN)
    intent = intent.transition_to(OrderStatus.VALIDATED)
    assert intent.status == OrderStatus.VALIDATED


def test_unknown_cannot_jump_to_submitting_directly():
    # A lookup can only observe what the venue actually recorded -- it can never re-enter
    # SUBMITTING, which represents "about to call the network," not an observation.
    assert can_transition(OrderStatus.UNKNOWN, OrderStatus.SUBMITTING) is False


def test_terminal_statuses_have_no_outgoing_transitions():
    terminal = (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.FAILED)
    for status in terminal:
        for candidate in OrderStatus:
            assert can_transition(status, candidate) is False


def test_transition_to_does_not_mutate_the_original_intent():
    intent = make_intent()
    validated = intent.transition_to(OrderStatus.VALIDATED)
    assert intent.status == OrderStatus.CREATED
    assert validated.status == OrderStatus.VALIDATED
