"""UnitOfWork: one atomic slice of execution-pipeline persistence.

`ARCHITECTURE.md`'s decision/execution flow says to "read current state, evaluate risk, reserve
cash/exposure, persist decision/assessment/intent and outbox event" inside one account-serialized
transaction, and to "not hold a database transaction open during network requests." This module
gives a future `ExecutionService` (Slice 5) the persistence primitives for that transaction --
saving an `OrderIntent`, its status transitions, `Fill`s and `LedgerTransaction`s -- so they commit
or roll back together. It does not itself call any exchange or orchestrate the order lifecycle.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.execution import Fill
from wallybot.domain.ledger import LedgerTransaction
from wallybot.domain.order import TERMINAL_STATUSES, OrderIntent, OrderStatus
from wallybot.infrastructure.models import (
    FillRow,
    LedgerAccountRow,
    LedgerPostingRow,
    LedgerTransactionRow,
    OrderIntentRow,
    OrderTransitionRow,
)


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_order_intent(self, intent: OrderIntent) -> None:
        self.session.add(
            OrderIntentRow(
                client_order_id=intent.client_order_id,
                account_id=intent.account_id,
                environment=intent.environment,
                venue=intent.instrument.venue,
                base=intent.instrument.base,
                quote=intent.instrument.quote,
                side=intent.side,
                kind=intent.kind,
                quantity=intent.quantity,
                limit_price=intent.limit_price,
                decision_id=intent.decision_id,
                idempotency_key=intent.idempotency_key,
                risk_assessment_id=intent.risk_assessment_id,
                config_versions=dict(intent.config_versions),
                created_at=intent.created_at,
                expires_at=intent.expires_at,
                status=intent.status,
            )
        )
        # Flush immediately: there is no ORM `relationship()` linking order_intents to fills/
        # transitions, so without this a later save_fill/update_order_status in the same unit of
        # work has no guaranteed insert ordering against this row despite the real DB-level FK.
        await self.session.flush()

    async def update_order_status(
        self,
        client_order_id: str,
        from_status: OrderStatus,
        to_status: OrderStatus,
        occurred_at: datetime,
    ) -> None:
        row = await self.session.get(OrderIntentRow, client_order_id)
        if row is None:
            raise ValueError(f"no such order_intent: {client_order_id}")
        row.status = to_status
        self.session.add(
            OrderTransitionRow(
                client_order_id=client_order_id,
                from_status=from_status,
                to_status=to_status,
                occurred_at=occurred_at,
            )
        )

    async def get_order_status(self, client_order_id: str) -> OrderStatus | None:
        row = await self.session.get(OrderIntentRow, client_order_id)
        return OrderStatus(row.status) if row is not None else None

    async def list_open_order_intents(
        self, environment: str, account_id: str | None = None
    ) -> list[tuple[str, str, str, str]]:
        """`(client_order_id, venue, account_id, environment)` for every non-terminal order in
        `environment` -- exactly what a reconciliation sweep needs, without requiring the full
        `Instrument` fidelity (tick sizes, etc.) this table doesn't carry. `account_id` narrows
        the sweep to one account, whose orders only its own gateway can look up."""
        query = select(
            OrderIntentRow.client_order_id,
            OrderIntentRow.venue,
            OrderIntentRow.account_id,
            OrderIntentRow.environment,
        ).where(
            OrderIntentRow.environment == environment,
            OrderIntentRow.status.not_in([status.value for status in TERMINAL_STATUSES]),
        )
        if account_id is not None:
            query = query.where(OrderIntentRow.account_id == account_id)
        result = await self.session.execute(query)
        return [row.tuple() for row in result.all()]

    async def fill_exists(
        self, venue: str, account_id: str, environment: str, fill_id: str
    ) -> bool:
        result = await self.session.execute(
            select(FillRow.id).where(
                FillRow.venue == venue,
                FillRow.account_id == account_id,
                FillRow.environment == environment,
                FillRow.fill_id == fill_id,
            )
        )
        return result.scalar_one_or_none() is not None

    def save_fill(self, fill: Fill, account_id: str, environment: str) -> None:
        self.session.add(
            FillRow(
                fill_id=fill.fill_id,
                client_order_id=fill.client_order_id,
                account_id=account_id,
                environment=environment,
                venue=fill.instrument.venue,
                base=fill.instrument.base,
                quote=fill.instrument.quote,
                side=fill.side,
                quantity=fill.quantity,
                price=fill.price,
                fee=fill.fee,
                fee_currency=fill.fee_currency,
                filled_at=fill.filled_at,
            )
        )

    async def save_ledger_transaction(self, transaction: LedgerTransaction) -> None:
        accounts: dict[tuple[str, str, str], LedgerAccountRow] = {}
        for posting in transaction.postings:
            key = (posting.account.account_id, posting.account.currency, posting.account.purpose)
            if key not in accounts:
                accounts[key] = await self._get_or_create_account(*key)

        self.session.add(
            LedgerTransactionRow(
                transaction_id=transaction.transaction_id,
                account_id=transaction.account_id,
                reason=transaction.reason,
                reference_id=transaction.reference_id,
                recorded_at=transaction.recorded_at,
            )
        )
        # Flush before adding postings: there is no ORM `relationship()` between the two mapped
        # classes, so the unit-of-work flush order between them is otherwise unspecified -- and
        # postings carry a real FK to this transaction row.
        await self.session.flush()
        for posting in transaction.postings:
            key = (posting.account.account_id, posting.account.currency, posting.account.purpose)
            self.session.add(
                LedgerPostingRow(
                    transaction_id=transaction.transaction_id,
                    ledger_account_id=accounts[key].id,
                    amount=posting.amount,
                )
            )

    async def _get_or_create_account(
        self, account_id: str, currency: str, purpose: str
    ) -> LedgerAccountRow:
        existing = (
            await self.session.execute(
                select(LedgerAccountRow).where(
                    LedgerAccountRow.account_id == account_id,
                    LedgerAccountRow.currency == currency,
                    LedgerAccountRow.purpose == purpose,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        row = LedgerAccountRow(account_id=account_id, currency=currency, purpose=purpose)
        self.session.add(row)
        await self.session.flush()
        return row


@asynccontextmanager
async def unit_of_work(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[UnitOfWork]:
    async with sessions.begin() as session:
        yield UnitOfWork(session)
