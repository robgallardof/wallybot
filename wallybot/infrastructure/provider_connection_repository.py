from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.models import ProviderConnectionRow


class ProviderConnectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: str) -> tuple[ProviderConnectionRow, ...]:
        rows = (
            await self.session.scalars(
                select(ProviderConnectionRow)
                .where(ProviderConnectionRow.user_id == user_id)
                .order_by(ProviderConnectionRow.created_at.desc())
            )
        ).all()
        return tuple(rows)

    async def add(self, connection: ProviderConnectionRow) -> None:
        self.session.add(connection)
