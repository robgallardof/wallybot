import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.execution_service import ExecutionService
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.domain.execution import SubmissionOutcome
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.models import OrderIntentRow

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_intent(client_order_id: str, **overrides: Any) -> OrderIntent:
    fields: dict[str, Any] = {
        "account_id": "acct-1",
        "environment": "PAPER",
        "instrument": None,
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


async def make_gateway_and_instrument(**scripts: Any):
    gateway = FakeExchange(
        clock=FixedClock(NOW),
        seed=1,
        balances={"USD": Decimal("1000000"), "BTC": Decimal("10")},
        **scripts,
    )
    instrument = (await gateway.discover_instruments())[0]
    return gateway, instrument


async def test_sweep_resolves_every_unknown_order_left_over_from_a_crash(sessions) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={
            "order-1": SubmissionOutcome.UNKNOWN,
            "order-2": SubmissionOutcome.UNKNOWN,
        }
    )
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    intent_1 = make_intent("order-1", instrument=instrument, quantity=instrument.min_quantity * 10)
    intent_2 = make_intent("order-2", instrument=instrument, quantity=instrument.min_quantity * 5)
    assert await execution.submit(intent_1) is OrderStatus.UNKNOWN
    assert await execution.submit(intent_2) is OrderStatus.UNKNOWN

    outcomes = await reconciliation.sweep("PAPER")
    assert len(outcomes) == 2
    resolved = {outcome.client_order_id: outcome for outcome in outcomes}
    assert resolved["order-1"].resolved_status is OrderStatus.FILLED
    assert resolved["order-1"].error is None
    assert resolved["order-2"].resolved_status is OrderStatus.FILLED
    assert resolved["order-2"].error is None

    async with sessions() as session:
        row_1 = await session.get(OrderIntentRow, "order-1")
        row_2 = await session.get(OrderIntentRow, "order-2")
        assert row_1 is not None and row_1.status == OrderStatus.FILLED
        assert row_2 is not None and row_2.status == OrderStatus.FILLED


async def test_sweep_ignores_terminal_orders_and_only_scopes_to_its_own_environment(
    sessions,
) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={"order-rejected": SubmissionOutcome.REJECTED}
    )
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    rejected = make_intent(
        "order-rejected", instrument=instrument, quantity=instrument.min_quantity * 10
    )
    assert await execution.submit(rejected) is OrderStatus.REJECTED

    filled = make_intent(
        "order-filled", instrument=instrument, quantity=instrument.min_quantity * 10
    )
    assert await execution.submit(filled) is OrderStatus.FILLED

    outcomes = await reconciliation.sweep("PAPER")
    assert outcomes == ()

    live_environment_outcomes = await reconciliation.sweep("LIVE")
    assert live_environment_outcomes == ()


async def test_sweep_records_one_orders_failure_without_aborting_the_rest(sessions) -> None:
    gateway, instrument = await make_gateway_and_instrument(
        submission_script={"order-1": SubmissionOutcome.UNKNOWN}
    )
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    intent = make_intent("order-1", instrument=instrument, quantity=instrument.min_quantity * 10)
    assert await execution.submit(intent) is OrderStatus.UNKNOWN

    # Corrupt this order's status to something the domain model forbids observing a lookup
    # transition into, so reconcile_order raises for it -- and confirm the sweep still reports
    # a per-order outcome rather than raising out of the whole sweep.
    async with sessions() as session:
        row = await session.get(OrderIntentRow, "order-1")
        assert row is not None
        row.status = OrderStatus.SUBMITTED
        await session.commit()

    outcomes = await reconciliation.sweep("PAPER")
    assert len(outcomes) == 1
    assert outcomes[0].client_order_id == "order-1"
    assert outcomes[0].resolved_status is None
    assert outcomes[0].error is not None
