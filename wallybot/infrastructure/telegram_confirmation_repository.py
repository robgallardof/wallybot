"""TelegramConfirmationRepository: persists `wallybot.domain.telegram_confirmation`.

`confirm` only succeeds against a currently pending, unexpired row -- same idempotent-guard shape
as `wallybot.infrastructure.breaker_repository.BreakerRepository.clear`.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.telegram_confirmation import (
    CONFIRMATION_TTL,
    TelegramAction,
    TelegramConfirmation,
)
from wallybot.infrastructure.models import TelegramConfirmationRow


class TelegramConfirmationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, action: TelegramAction, now: datetime, id_generator: IdGenerator
    ) -> TelegramConfirmation:
        confirmation = TelegramConfirmation(
            confirmation_id=id_generator.new_id(),
            action=action,
            requested_at=now,
            expires_at=now + CONFIRMATION_TTL,
        )
        self.session.add(
            TelegramConfirmationRow(
                confirmation_id=confirmation.confirmation_id,
                action=confirmation.action.value,
                requested_at=confirmation.requested_at,
                expires_at=confirmation.expires_at,
            )
        )
        return confirmation

    async def get(self, confirmation_id: str) -> TelegramConfirmation | None:
        row = await self.session.get(TelegramConfirmationRow, confirmation_id)
        return None if row is None else self._to_domain(row)

    async def list_pending(self, now: datetime) -> tuple[TelegramConfirmation, ...]:
        rows = (
            (
                await self.session.execute(
                    select(TelegramConfirmationRow)
                    .where(
                        TelegramConfirmationRow.confirmed_at.is_(None),
                        TelegramConfirmationRow.expires_at > now,
                    )
                    .order_by(TelegramConfirmationRow.requested_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    async def confirm(self, confirmation_id: str, confirmed_by: str, now: datetime) -> bool:
        existing = await self.session.get(TelegramConfirmationRow, confirmation_id)
        if existing is None or existing.confirmed_at is not None or now >= existing.expires_at:
            return False
        existing.confirmed_at = now
        existing.confirmed_by = confirmed_by
        return True

    def _to_domain(self, row: TelegramConfirmationRow) -> TelegramConfirmation:
        return TelegramConfirmation(
            confirmation_id=row.confirmation_id,
            action=TelegramAction(row.action),
            requested_at=row.requested_at,
            expires_at=row.expires_at,
            confirmed_at=row.confirmed_at,
            confirmed_by=row.confirmed_by,
        )
