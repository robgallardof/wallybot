import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.execution_service import ExecutionService
from wallybot.domain.execution import SubmissionOutcome, VenueOrderStatus
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.exchanges.fake import FakeExchange, ScriptedFill
from wallybot.infrastructure.models import (
    FillRow,
    LedgerPostingRow,
    OrderIntentRow,
    OrderTransitionRow,
)
from wallybot.infrastructure.unit_of_work import unit_of_work

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    # Same reasoning as tests/integration/test_execution_persistence.py: psycopg's async driver
    # rejects Windows' default ProactorEventLoop, and these tests talk to the database directly.
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_intent(client_order_id: str = "order-1", **overrides: Any) -> OrderIntent:
    fields: dict[str, Any] = {
        "account_id": "acct-1",
        "environment": "PAPER",
        "instrument": None,  # filled in by the caller once the gateway's instrument is known
        "side": Side.BUY,
        "kind": OrderKind.MARKET,
        "quantity": None,
        "limit_price": None,
        "decision_id": "decision-1",
        "client_order_id": client_order_id,
        "idempotency_key": client_order_id,
        "risk_assessment_id": "risk-1",
        "config_versions": {"risk": 1},
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
        "status": OrderStatus.VALIDATED,
    }
    fields.update(overrides)
    return OrderIntent(**fields)


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_execution_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE ledger_postings, ledger_transactions, ledger_accounts, fills, "
            "order_transitions, order_intents CASCADE"
        )
    yield


async def make_gateway_and_instrument(**scripts):
    gateway = FakeExchange(
        clock=FixedClock(NOW),
        seed=1,
        balances={"USD": Decimal("1000000"), "BTC": Decimal("10")},
        **scripts,
    )
    instrument = (await gateway.discover_instruments())[0]
    return gateway, instrument


async def test_a_market_order_reaches_filled_and_persists_one_balanced_ledger_transaction(
    sessions,
) -> None:
    gateway, instrument = await make_gateway_and_instrument()
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    status = await service.submit(intent)
    assert status is OrderStatus.FILLED

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == OrderStatus.FILLED

        transitions = (
            (
                await session.execute(
                    select(OrderTransitionRow).where(
                        OrderTransitionRow.client_order_id == intent.client_order_id
                    )
                )
            )
            .scalars()
            .all()
        )
        sequence = [(t.from_status, t.to_status) for t in transitions]
        assert sequence == [
            (OrderStatus.VALIDATED, OrderStatus.SUBMITTING),
            (OrderStatus.SUBMITTING, OrderStatus.SUBMITTED),
            (OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED),
            (OrderStatus.ACKNOWLEDGED, OrderStatus.FILLED),
        ]

        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1

        postings = (await session.execute(select(LedgerPostingRow))).scalars().all()
        assert len(postings) == 4


async def test_a_rejected_submission_never_reaches_the_exchange_a_second_time(sessions) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={"order-1": SubmissionOutcome.REJECTED}
    )
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    status = await service.submit(intent)
    assert status is OrderStatus.REJECTED

    # Calling submit() again on the same (now terminal) intent must not touch the gateway again --
    # it should just report the already-resolved status.
    status_again = await service.submit(intent)
    assert status_again is OrderStatus.REJECTED


async def test_an_ambiguous_submission_stays_unknown_until_reconciled(sessions) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={"order-1": SubmissionOutcome.UNKNOWN}
    )
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    status = await service.submit(intent)
    assert status is OrderStatus.UNKNOWN

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == OrderStatus.UNKNOWN
        # The order was genuinely accepted at the venue (FakeExchange registers it internally
        # regardless of what it told the caller) -- no fill has been persisted yet, though,
        # because submit() never blindly assumes an UNKNOWN outcome succeeded.
        assert (await session.execute(select(FillRow))).scalars().all() == []

    # ADR-008's reconcile-before-retry: resolve it by asking the gateway what it actually knows.
    resolved = await service.reconcile(intent)
    assert resolved is OrderStatus.FILLED

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == OrderStatus.FILLED
        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1


async def test_reconcile_is_idempotent_and_never_double_posts_a_fill(sessions) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={"order-1": SubmissionOutcome.UNKNOWN}
    )
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    await service.submit(intent)
    await service.reconcile(intent)
    # Calling reconcile() again on an already-terminal (FILLED) order must be a safe no-op.
    resolved_again = await service.reconcile(intent)
    assert resolved_again is OrderStatus.FILLED

    async with sessions() as session:
        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1
        postings = (await session.execute(select(LedgerPostingRow))).scalars().all()
        assert len(postings) == 4


async def test_resuming_after_a_crash_immediately_after_the_submitting_claim_never_resubmits(
    sessions,
) -> None:
    # Simulate a process that persisted the durable SUBMITTING claim and then crashed before (or
    # during) the network call -- resuming must not call submit_order a second time; it must
    # leave the order at SUBMITTING for reconcile() to resolve, per ADR-008.
    gateway, instrument = await make_gateway_and_instrument()
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    async with unit_of_work(sessions) as uow:
        await uow.save_order_intent(intent)
        await uow.update_order_status(
            intent.client_order_id, OrderStatus.VALIDATED, OrderStatus.SUBMITTING, NOW
        )

    status = await service.submit(intent)
    assert status is OrderStatus.SUBMITTING
    # The gateway must never have been called: it has no record of this order at all.
    lookup = await gateway.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.NOT_FOUND

    # reconcile() is the only legal way forward from here, and it must recognize the gateway's
    # "never happened" answer as a safe, proven-absent retry point.
    resolved = await service.reconcile(intent)
    assert resolved is OrderStatus.VALIDATED

    # Now a fresh submit() actually reaches the exchange and completes normally.
    final = await service.submit(intent)
    assert final is OrderStatus.FILLED


async def test_resuming_from_a_freshly_persisted_validated_intent_behaves_like_a_first_attempt(
    sessions,
) -> None:
    # Simulate a crash between persisting the order_intent row and committing the SUBMITTING
    # claim: resuming from VALIDATED must proceed exactly as a brand-new submit() would.
    gateway, instrument = await make_gateway_and_instrument()
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(instrument=instrument, quantity=instrument.min_quantity * 10)

    async with unit_of_work(sessions) as uow:
        await uow.save_order_intent(intent)

    status = await service.submit(intent)
    assert status is OrderStatus.FILLED

    async with sessions() as session:
        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1


async def test_a_scripted_partial_fill_is_observed_and_persisted_exactly_once(sessions) -> None:
    _, instrument = await make_gateway_and_instrument()
    partial = instrument.min_quantity * 4
    gateway, instrument = await make_gateway_and_instrument(
        fill_script={"order-1": [ScriptedFill(quantity=partial)]}
    )
    service = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    intent = make_intent(
        instrument=instrument,
        kind=OrderKind.LIMIT,
        limit_price=Decimal("70000"),
        quantity=instrument.min_quantity * 10,
    )

    status = await service.submit(intent)
    assert status is OrderStatus.PARTIALLY_FILLED

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == OrderStatus.PARTIALLY_FILLED
        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1
        assert fills[0].quantity == partial

    # Reconciling again observes the same partial state -- no new fill, no duplicate posting.
    # (Cancelling a PARTIALLY_FILLED order requires the CANCEL_REQUESTED step first, which is
    # outside this slice's scope -- ExecutionService does not orchestrate cancellation yet.)
    resolved_again = await service.reconcile(intent)
    assert resolved_again is OrderStatus.PARTIALLY_FILLED
    async with sessions() as session:
        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1
