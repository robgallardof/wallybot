"""Persisted delivery watermark for grouped, operator-owned proposal digests."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.models import AiProposalDigestRow


class AiProposalDigestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def last_sent_at(self, owner_id: str) -> datetime | None:
        row = await self.session.get(AiProposalDigestRow, owner_id)
        return None if row is None else row.last_sent_at

    async def mark_sent(self, owner_id: str, now: datetime) -> None:
        row = await self.session.get(AiProposalDigestRow, owner_id, with_for_update=True)
        if row is None:
            self.session.add(AiProposalDigestRow(owner_id=owner_id, last_sent_at=now))
        else:
            row.last_sent_at = now
