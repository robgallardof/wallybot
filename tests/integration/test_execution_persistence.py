import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.execution import Fill
from wallybot.domain.ledger import AccountPurpose, LedgerAccount, LedgerPosting, LedgerTransaction
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.infrastructure.models import FillRow, OrderIntentRow
from wallybot.infrastructure.unit_of_work import unit_of_work

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    # Psycopg's async driver refuses Windows' default ProactorEventLoop; every other integration
    # test avoids this by routing through TestClient's own selector_loop, but these tests talk to
    # the database directly, so the loop itself needs to be a selector loop here.
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


def make_intent(
    client_order_id: str = "order-1", idempotency_key: str | None = None
) -> OrderIntent:
    return OrderIntent(
        account_id="acct-1",
        environment="PAPER",
        instrument=INSTRUMENT,
        side=Side.BUY,
        kind=OrderKind.MARKET,
        quantity=Decimal("0.01"),
        limit_price=None,
        decision_id="decision-1",
        client_order_id=client_order_id,
        idempotency_key=idempotency_key or client_order_id,
        risk_assessment_id="risk-1",
        config_versions={"risk": 1},
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )


@pytest.fixture
def sessions(settings, dependencies):
    # settings triggers migrations (session-scoped, runs once); the new tables are granted only
    # to wally_worker, not wally_api, so this connects with the raw superuser URL testcontainers
    # created them under -- adequate for testing the schema/constraints themselves.
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


async def test_order_intent_round_trips_and_records_transitions(sessions) -> None:
    intent = make_intent()
    async with unit_of_work(sessions) as uow:
        await uow.save_order_intent(intent)

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == OrderStatus.CREATED
        assert row.quantity == intent.quantity

    validated = intent.transition_to(OrderStatus.VALIDATED)
    async with unit_of_work(sessions) as uow:
        await uow.update_order_status(
            intent.client_order_id, OrderStatus.CREATED, OrderStatus.VALIDATED, NOW
        )

    async with sessions() as session:
        row = await session.get(OrderIntentRow, intent.client_order_id)
        assert row is not None
        assert row.status == validated.status


async def test_duplicate_idempotency_key_is_rejected(sessions) -> None:
    first = make_intent(client_order_id="order-a", idempotency_key="idem-1")
    async with unit_of_work(sessions) as uow:
        await uow.save_order_intent(first)

    second = make_intent(client_order_id="order-b", idempotency_key="idem-1")
    with pytest.raises(IntegrityError):
        async with unit_of_work(sessions) as uow:
            await uow.save_order_intent(second)


async def test_duplicate_fill_is_rejected(sessions) -> None:
    intent = make_intent()
    fill = Fill(
        fill_id="fill-1",
        client_order_id=intent.client_order_id,
        instrument=INSTRUMENT,
        side=Side.BUY,
        quantity=Decimal("0.01"),
        price=Decimal("60000"),
        fee=Decimal("0.60"),
        fee_currency="USD",
        filled_at=NOW,
    )
    async with unit_of_work(sessions) as uow:
        await uow.save_order_intent(intent)
        uow.save_fill(fill, account_id=intent.account_id, environment=intent.environment)

    async with sessions() as session:
        rows = (await session.execute(select(FillRow))).scalars().all()
        assert len(rows) == 1

    with pytest.raises(IntegrityError):
        async with unit_of_work(sessions) as uow:
            uow.save_fill(fill, account_id=intent.account_id, environment=intent.environment)


async def test_ledger_transaction_round_trip_creates_accounts_and_postings(sessions) -> None:
    cash = LedgerAccount(account_id="acct-1", currency="USD", purpose=AccountPurpose.CASH)
    clearing = LedgerAccount(account_id="clearing", currency="USD", purpose=AccountPurpose.CLEARING)
    transaction = LedgerTransaction(
        transaction_id="tx-1",
        account_id="acct-1",
        reason="FILL",
        reference_id="fill-1",
        postings=(
            LedgerPosting(account=cash, amount=Decimal("-600.06")),
            LedgerPosting(account=clearing, amount=Decimal("600.06")),
        ),
        recorded_at=NOW,
    )
    async with unit_of_work(sessions) as uow:
        await uow.save_ledger_transaction(transaction)

    async with sessions() as session:
        from wallybot.infrastructure.models import LedgerAccountRow, LedgerPostingRow

        accounts = (await session.execute(select(LedgerAccountRow))).scalars().all()
        postings = (await session.execute(select(LedgerPostingRow))).scalars().all()
        assert len(accounts) == 2
        assert len(postings) == 2
        assert sum(p.amount for p in postings) == 0


async def test_duplicate_ledger_reference_is_rejected(sessions) -> None:
    cash = LedgerAccount(account_id="acct-1", currency="USD", purpose=AccountPurpose.CASH)
    clearing = LedgerAccount(account_id="clearing", currency="USD", purpose=AccountPurpose.CLEARING)

    def build(transaction_id: str) -> LedgerTransaction:
        return LedgerTransaction(
            transaction_id=transaction_id,
            account_id="acct-1",
            reason="FILL",
            reference_id="fill-1",
            postings=(
                LedgerPosting(account=cash, amount=Decimal("-1")),
                LedgerPosting(account=clearing, amount=Decimal("1")),
            ),
            recorded_at=NOW,
        )

    async with unit_of_work(sessions) as uow:
        await uow.save_ledger_transaction(build("tx-1"))

    with pytest.raises(IntegrityError):
        async with unit_of_work(sessions) as uow:
            await uow.save_ledger_transaction(build("tx-2"))
