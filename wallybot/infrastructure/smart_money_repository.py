"""SmartMoneyScoreRepository: append-only persistence for Smart Money score history.

`save` always inserts a new row -- there is no update path at all, matching ARCHITECTURE.md's
"store the score history... never overwrite previous score snapshots" as a structural guarantee,
not a convention a future change could accidentally break.
"""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.smart_money import SmartMoneyScoreSnapshot, SmartMoneyStatus
from wallybot.infrastructure.models import SmartMoneyScoreSnapshotRow


class SmartMoneyScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, snapshot: SmartMoneyScoreSnapshot) -> None:
        self.session.add(
            SmartMoneyScoreSnapshotRow(
                wallet_id=snapshot.wallet_id,
                version=snapshot.version,
                status=snapshot.status,
                score=snapshot.score,
                trade_count=snapshot.trade_count,
                win_rate=snapshot.win_rate,
                realized_pnl_usd=snapshot.realized_pnl_usd,
                wallet_age_seconds=(
                    Decimal(str(snapshot.wallet_age.total_seconds()))
                    if snapshot.wallet_age is not None
                    else None
                ),
                computed_at=snapshot.computed_at,
                reasons=list(snapshot.reasons),
            )
        )

    async def latest(self, wallet_id: str) -> SmartMoneyScoreSnapshot | None:
        row = (
            await self.session.execute(
                select(SmartMoneyScoreSnapshotRow)
                .where(SmartMoneyScoreSnapshotRow.wallet_id == wallet_id)
                .order_by(SmartMoneyScoreSnapshotRow.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def list_latest(self) -> tuple[SmartMoneyScoreSnapshot, ...]:
        """One row per wallet: its most recent snapshot, newest-scored wallet first. Backs a
        UI/API listing -- per-wallet history stays available via `history`."""
        rows = (
            (
                await self.session.execute(
                    select(SmartMoneyScoreSnapshotRow)
                    .distinct(SmartMoneyScoreSnapshotRow.wallet_id)
                    .order_by(
                        SmartMoneyScoreSnapshotRow.wallet_id,
                        SmartMoneyScoreSnapshotRow.computed_at.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(
            sorted(
                (self._to_domain(row) for row in rows),
                key=lambda snapshot: snapshot.computed_at,
                reverse=True,
            )
        )

    async def history(self, wallet_id: str) -> tuple[SmartMoneyScoreSnapshot, ...]:
        rows = (
            (
                await self.session.execute(
                    select(SmartMoneyScoreSnapshotRow)
                    .where(SmartMoneyScoreSnapshotRow.wallet_id == wallet_id)
                    .order_by(SmartMoneyScoreSnapshotRow.computed_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: SmartMoneyScoreSnapshotRow) -> SmartMoneyScoreSnapshot:
        return SmartMoneyScoreSnapshot(
            wallet_id=row.wallet_id,
            version=row.version,
            status=SmartMoneyStatus(row.status),
            score=row.score,
            trade_count=row.trade_count,
            win_rate=row.win_rate,
            realized_pnl_usd=row.realized_pnl_usd,
            wallet_age=(
                None
                if row.wallet_age_seconds is None
                else timedelta(seconds=float(row.wallet_age_seconds))
            ),
            computed_at=row.computed_at,
            reasons=tuple(row.reasons),
        )
