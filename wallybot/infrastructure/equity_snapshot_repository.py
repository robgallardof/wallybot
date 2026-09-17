"""EquitySnapshotRepository: append-only persistence for equity history.

`recent` bounds its query to a window rather than the full history -- `wallybot.domain.equity`'s
daily/weekly loss only ever need the last ~8 days, and drawdown only needs the latest row's own
`high_water_mark`, never a full scan.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.equity import EquitySnapshot
from wallybot.infrastructure.models import EquitySnapshotRow


class EquitySnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, snapshot: EquitySnapshot) -> None:
        self.session.add(
            EquitySnapshotRow(
                account_id=snapshot.account_id,
                environment=snapshot.environment,
                equity=snapshot.equity,
                high_water_mark=snapshot.high_water_mark,
                recorded_at=snapshot.recorded_at,
            )
        )

    async def latest(self, account_id: str, environment: str) -> EquitySnapshot | None:
        row = (
            await self.session.execute(
                select(EquitySnapshotRow)
                .where(
                    EquitySnapshotRow.account_id == account_id,
                    EquitySnapshotRow.environment == environment,
                )
                .order_by(EquitySnapshotRow.recorded_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def recent(
        self, account_id: str, environment: str, since: datetime
    ) -> tuple[EquitySnapshot, ...]:
        rows = (
            (
                await self.session.execute(
                    select(EquitySnapshotRow)
                    .where(
                        EquitySnapshotRow.account_id == account_id,
                        EquitySnapshotRow.environment == environment,
                        EquitySnapshotRow.recorded_at >= since,
                    )
                    .order_by(EquitySnapshotRow.recorded_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: EquitySnapshotRow) -> EquitySnapshot:
        return EquitySnapshot(
            account_id=row.account_id,
            environment=row.environment,
            equity=row.equity,
            high_water_mark=row.high_water_mark,
            recorded_at=row.recorded_at,
        )
