"""ProviderReliabilityRepository: append-only persistence for provider reliability snapshots.

`save` always inserts a new row -- same insert-only discipline as every other snapshot table in
this schema.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.provider_reliability import (
    ProviderReliabilitySnapshot,
    ProviderReliabilityStatus,
)
from wallybot.infrastructure.models import ProviderReliabilitySnapshotRow


class ProviderReliabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, snapshot: ProviderReliabilitySnapshot) -> None:
        self.session.add(
            ProviderReliabilitySnapshotRow(
                provider=snapshot.provider,
                status=snapshot.status,
                call_count=snapshot.call_count,
                error_rate=snapshot.error_rate,
                average_latency_ms=snapshot.average_latency_ms,
                seconds_since_last_success=snapshot.seconds_since_last_success,
                reasons=list(snapshot.reasons),
                computed_at=snapshot.computed_at,
            )
        )

    async def latest(self, provider: str) -> ProviderReliabilitySnapshot | None:
        row = (
            await self.session.execute(
                select(ProviderReliabilitySnapshotRow)
                .where(ProviderReliabilitySnapshotRow.provider == provider)
                .order_by(ProviderReliabilitySnapshotRow.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def list_latest(self) -> tuple[ProviderReliabilitySnapshot, ...]:
        """One row per provider: its most recent snapshot, newest-computed provider first. Backs
        a UI/API listing -- per-provider history stays available via `history`."""
        rows = (
            (
                await self.session.execute(
                    select(ProviderReliabilitySnapshotRow)
                    .distinct(ProviderReliabilitySnapshotRow.provider)
                    .order_by(
                        ProviderReliabilitySnapshotRow.provider,
                        ProviderReliabilitySnapshotRow.computed_at.desc(),
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

    async def history(self, provider: str) -> tuple[ProviderReliabilitySnapshot, ...]:
        rows = (
            (
                await self.session.execute(
                    select(ProviderReliabilitySnapshotRow)
                    .where(ProviderReliabilitySnapshotRow.provider == provider)
                    .order_by(ProviderReliabilitySnapshotRow.computed_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: ProviderReliabilitySnapshotRow) -> ProviderReliabilitySnapshot:
        return ProviderReliabilitySnapshot(
            provider=row.provider,
            status=ProviderReliabilityStatus(row.status),
            call_count=row.call_count,
            error_rate=row.error_rate,
            average_latency_ms=row.average_latency_ms,
            seconds_since_last_success=row.seconds_since_last_success,
            computed_at=row.computed_at,
            reasons=tuple(row.reasons),
        )
