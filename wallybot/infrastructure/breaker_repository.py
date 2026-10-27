"""BreakerRepository: one mutable latch row per `BreakerType`.

`trip` is idempotent -- a repeated trip while already active keeps the original reason/time,
matching `wallybot.domain.breaker`'s own documented semantics (never overwrite an active breaker's
evidence with a later, possibly-less-informative one). `clear` only succeeds against a currently
active breaker.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.breaker import Breaker, BreakerType
from wallybot.infrastructure.models import BreakerRow


class BreakerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def trip(self, breaker_type: BreakerType, reason: str, now: datetime) -> None:
        existing = await self.session.get(BreakerRow, breaker_type.value)
        if existing is not None and existing.cleared_at is None:
            return
        if existing is None:
            self.session.add(
                BreakerRow(breaker_type=breaker_type.value, reason=reason, tripped_at=now)
            )
        else:
            existing.reason = reason
            existing.tripped_at = now
            existing.cleared_at = None
            existing.cleared_by = None

    async def clear(self, breaker_type: BreakerType, cleared_by: str, now: datetime) -> bool:
        existing = await self.session.get(BreakerRow, breaker_type.value)
        if existing is None or existing.cleared_at is not None:
            return False
        existing.cleared_at = now
        existing.cleared_by = cleared_by
        return True

    async def list_active(self) -> tuple[Breaker, ...]:
        rows = (
            (await self.session.execute(select(BreakerRow).where(BreakerRow.cleared_at.is_(None))))
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    async def list_all(self) -> tuple[Breaker, ...]:
        rows = (
            (await self.session.execute(select(BreakerRow).order_by(BreakerRow.breaker_type)))
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: BreakerRow) -> Breaker:
        return Breaker(
            breaker_type=BreakerType(row.breaker_type),
            reason=row.reason,
            tripped_at=row.tripped_at,
            cleared_at=row.cleared_at,
            cleared_by=row.cleared_by,
        )
