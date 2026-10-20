"""Read-only queries for the portfolio ledger.

The API deliberately reads the ledger rather than an exchange credential.  That keeps this
surface inside the no-execution boundary and makes every displayed balance auditable.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.models import FillRow, LedgerAccountRow, LedgerPostingRow


@dataclass(frozen=True)
class LedgerBalance:
    currency: str
    purpose: str
    amount: Decimal


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_balances(self, account_id: str) -> tuple[LedgerBalance, ...]:
        statement = (
            select(
                LedgerAccountRow.currency,
                LedgerAccountRow.purpose,
                func.coalesce(func.sum(LedgerPostingRow.amount), 0).label("amount"),
            )
            .outerjoin(
                LedgerPostingRow,
                LedgerPostingRow.ledger_account_id == LedgerAccountRow.id,
            )
            .where(LedgerAccountRow.account_id == account_id)
            .group_by(LedgerAccountRow.currency, LedgerAccountRow.purpose)
            .order_by(LedgerAccountRow.purpose, LedgerAccountRow.currency)
        )
        rows = (await self.session.execute(statement)).all()
        return tuple(
            LedgerBalance(currency=row.currency, purpose=row.purpose, amount=Decimal(row.amount))
            for row in rows
            if row.amount != 0
        )

    async def list_recent_fills(
        self, account_id: str, limit: int = 50, environment: str = "PAPER"
    ) -> tuple[FillRow, ...]:
        rows = (
            await self.session.scalars(
                select(FillRow)
                .where(FillRow.account_id == account_id, FillRow.environment == environment)
                .order_by(FillRow.filled_at.desc(), FillRow.id.desc())
                .limit(limit)
            )
        ).all()
        return tuple(rows)

    async def sum_fees_since(
        self,
        account_id: str,
        since: datetime,
        environment: str = "PAPER",
        currency: str | None = None,
    ) -> Decimal:
        """Total fees paid on fills at or after `since` -- bounded by the date range (not the
        full table), for the Telegram report's costs section (PENDING.md Fase 8)."""
        statement = select(func.coalesce(func.sum(FillRow.fee), 0)).where(
            FillRow.account_id == account_id,
            FillRow.environment == environment,
            FillRow.filled_at >= since,
        )
        if currency is not None:
            statement = statement.where(FillRow.fee_currency == currency)
        total = await self.session.scalar(statement)
        return Decimal(total) if total is not None else Decimal(0)
