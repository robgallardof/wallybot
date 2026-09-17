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

    async def latest_with_key(self, provider: str) -> ProviderConnectionRow | None:
        """Most recently added connection for `provider` that actually has a key stored --
        an operator adding one through the Connections UI is enough for a consumer (e.g.
        `wallybot.application.price_consensus_job`) to start using it, no restart needed.
        Across any user: this app has one operator in practice, and a connection's owner is
        who added it, not a scope the consumer needs to filter by."""
        return await self.session.scalar(
            select(ProviderConnectionRow)
            .where(
                ProviderConnectionRow.provider == provider,
                ProviderConnectionRow.encrypted_key.is_not(None),
            )
            .order_by(ProviderConnectionRow.created_at.desc())
            .limit(1)
        )
