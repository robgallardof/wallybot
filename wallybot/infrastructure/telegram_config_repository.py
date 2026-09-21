from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.models import TelegramConfigRow


class TelegramConfigRepository:
    """Reads/writes the singleton `telegram_config` row (id=1). Never decrypts the bot token --
    only the caller (equipped with `Crypto`) does that, and only when actually sending."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> TelegramConfigRow | None:
        return await self.session.get(TelegramConfigRow, 1)

    async def upsert(
        self, encrypted_bot_token: str | None, chat_id: int | None, enabled: bool
    ) -> TelegramConfigRow:
        row = await self.session.get(TelegramConfigRow, 1, with_for_update=True)
        if row is None:
            row = TelegramConfigRow(id=1)
            self.session.add(row)
        if encrypted_bot_token is not None:
            row.encrypted_bot_token = encrypted_bot_token
        row.chat_id = chat_id
        row.enabled = enabled
        return row

    async def set_last_update_id(self, last_update_id: int) -> None:
        row = await self.session.get(TelegramConfigRow, 1, with_for_update=True)
        if row is not None:
            row.last_update_id = last_update_id
