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
        self,
        encrypted_bot_token: str | None,
        chat_id: int | None,
        enabled: bool,
        *,
        pairing_code_hash: str | None = None,
        begin_pairing: bool = False,
    ) -> TelegramConfigRow:
        row = await self.session.get(TelegramConfigRow, 1, with_for_update=True)
        if row is None:
            row = TelegramConfigRow(id=1)
            self.session.add(row)
        if encrypted_bot_token is not None:
            row.encrypted_bot_token = encrypted_bot_token
        if begin_pairing:
            # A bot-token change must never leave the old bot's chat allowlisted. Resetting the
            # cursor also lets the new bot receive its own /start update.
            row.chat_id = None
            row.last_update_id = None
            row.pairing_code_hash = pairing_code_hash
        elif chat_id is not None:
            # Manual entry remains an escape hatch for groups, but completing it revokes any
            # previous pairing code so an intercepted old code cannot replace the destination.
            row.chat_id = chat_id
            row.pairing_code_hash = None
        row.enabled = enabled
        return row

    async def complete_pairing(self, chat_id: int, last_update_id: int) -> bool:
        """Atomically allowlist a chat after its exact pending pairing code was verified."""
        row = await self.session.get(TelegramConfigRow, 1, with_for_update=True)
        if row is None or row.pairing_code_hash is None:
            return False
        row.chat_id = chat_id
        row.pairing_code_hash = None
        row.last_update_id = last_update_id
        return True

    async def set_last_update_id(self, last_update_id: int) -> None:
        row = await self.session.get(TelegramConfigRow, 1, with_for_update=True)
        if row is not None:
            row.last_update_id = last_update_id
