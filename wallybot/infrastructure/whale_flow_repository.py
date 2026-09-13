"""WhaleTransferRepository: append-only persistence for detected whale transfer signals.

`save` always inserts a new row -- no update path at all, matching the insert-only discipline
already used for `SmartMoneyClusterSignalRow`/`SmartMoneyScoreSnapshotRow`/`TokenRiskScoreRow`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.wallet_activity import OnChainActionType
from wallybot.domain.whale_flow import WhaleTransferSignal
from wallybot.infrastructure.models import WhaleTransferSignalRow


class WhaleTransferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, signal: WhaleTransferSignal) -> None:
        self.session.add(
            WhaleTransferSignalRow(
                wallet_id=signal.wallet_id,
                chain=signal.chain,
                token=signal.token,
                action=signal.action,
                amount=signal.amount,
                value_usd=signal.value_usd,
                threshold_usd=signal.threshold_usd,
                occurred_at=signal.occurred_at,
                reasons=list(signal.reasons),
            )
        )

    async def history_for_wallet(self, wallet_id: str) -> tuple[WhaleTransferSignal, ...]:
        rows = (
            (
                await self.session.execute(
                    select(WhaleTransferSignalRow)
                    .where(WhaleTransferSignalRow.wallet_id == wallet_id)
                    .order_by(WhaleTransferSignalRow.occurred_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    async def latest(self) -> tuple[WhaleTransferSignal, ...]:
        rows = (
            (
                await self.session.execute(
                    select(WhaleTransferSignalRow).order_by(
                        WhaleTransferSignalRow.occurred_at.desc()
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: WhaleTransferSignalRow) -> WhaleTransferSignal:
        return WhaleTransferSignal(
            wallet_id=row.wallet_id,
            chain=row.chain,
            token=row.token,
            action=OnChainActionType(row.action),
            amount=row.amount,
            value_usd=row.value_usd,
            threshold_usd=row.threshold_usd,
            occurred_at=row.occurred_at,
            reasons=tuple(row.reasons),
        )
