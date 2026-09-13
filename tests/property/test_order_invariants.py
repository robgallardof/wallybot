from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side, can_transition

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


def make_intent() -> OrderIntent:
    return OrderIntent(
        account_id="acct-1",
        environment="PAPER",
        instrument=INSTRUMENT,
        side=Side.BUY,
        kind=OrderKind.MARKET,
        quantity=Decimal("0.01"),
        limit_price=None,
        decision_id="decision-1",
        client_order_id="client-1",
        idempotency_key="idem-1",
        risk_assessment_id="risk-1",
        config_versions={"risk_policy": 1},
        created_at=CREATED_AT,
        expires_at=CREATED_AT + timedelta(minutes=5),
    )


@given(picks=st.lists(st.integers(min_value=0, max_value=9), max_size=30))
@settings(max_examples=200)
def test_any_walk_of_only_legal_transitions_never_produces_an_illegal_state(picks):
    """A random walk that only ever takes a move can_transition already approves must never
    raise, must never leave a terminal status, and must always match docs/diagrams/order-
    lifecycle.md's edges -- the same style as test_control_sequence_never_enters_live for the
    Control state machine.
    """
    intent = make_intent()
    for pick in picks:
        if intent.is_terminal:
            for candidate in OrderStatus:
                assert can_transition(intent.status, candidate) is False
            break
        legal_moves = sorted(
            candidate for candidate in OrderStatus if can_transition(intent.status, candidate)
        )
        if not legal_moves:
            break
        next_status = legal_moves[pick % len(legal_moves)]
        intent = intent.transition_to(next_status)
        assert intent.status == next_status
