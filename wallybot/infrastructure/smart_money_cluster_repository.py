"""SmartMoneyClusterRepository: append-only persistence for Smart Money cluster signals.

`save` always inserts a new row -- no update path exists at all, matching
`SmartMoneyScoreRepository`'s "never overwrite previous score snapshots" discipline: each
detection run's output is a fact about a moment in time, never a correction of an earlier one.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.smart_money_cluster import SmartMoneyClusterSignal
from wallybot.domain.wallet_activity import OnChainActionType
from wallybot.infrastructure.models import SmartMoneyClusterSignalRow


class SmartMoneyClusterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, signal: SmartMoneyClusterSignal) -> None:
        self.session.add(
            SmartMoneyClusterSignalRow(
                token=signal.token,
                chain=signal.chain,
                action=signal.action,
                window_start=signal.window_start,
                window_end=signal.window_end,
                wallet_ids=list(signal.wallet_ids),
                independent_wallet_count=signal.independent_wallet_count,
                total_value_usd=signal.total_value_usd,
                average_entry_price=signal.average_entry_price,
                independence_score=signal.independence_score,
                confidence=signal.confidence,
                reasons=list(signal.reasons),
            )
        )

    async def history_for_token(
        self, chain: str, token: str
    ) -> tuple[SmartMoneyClusterSignal, ...]:
        rows = (
            (
                await self.session.execute(
                    select(SmartMoneyClusterSignalRow)
                    .where(
                        SmartMoneyClusterSignalRow.chain == chain,
                        SmartMoneyClusterSignalRow.token == token,
                    )
                    .order_by(SmartMoneyClusterSignalRow.window_end)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    async def latest(self) -> tuple[SmartMoneyClusterSignal, ...]:
        rows = (
            (
                await self.session.execute(
                    select(SmartMoneyClusterSignalRow).order_by(
                        SmartMoneyClusterSignalRow.window_end.desc()
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: SmartMoneyClusterSignalRow) -> SmartMoneyClusterSignal:
        return SmartMoneyClusterSignal(
            token=row.token,
            chain=row.chain,
            action=OnChainActionType(row.action),
            window_start=row.window_start,
            window_end=row.window_end,
            wallet_ids=tuple(row.wallet_ids),
            independent_wallet_count=row.independent_wallet_count,
            total_value_usd=row.total_value_usd,
            average_entry_price=row.average_entry_price,
            independence_score=row.independence_score,
            confidence=row.confidence,
            reasons=tuple(row.reasons),
        )
