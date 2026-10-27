"""TelegramReportRepository: tracks whether the current daily/weekly Telegram report has already
been sent, backed by `TelegramReportRow` (migration 0031). `wallybot.application.
telegram_report_job` compares `last_sent_key` against the tick's own computed period key
('YYYY-MM-DD' for daily, ISO 'YYYY-Www' for weekly) to decide whether to build and send a fresh
report."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.models import TelegramReportRow


class TelegramReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def last_sent_key(self, period: str) -> str | None:
        row = await self.session.get(TelegramReportRow, period)
        return None if row is None else row.last_sent_key

    async def mark_sent(self, period: str, key: str, now: datetime) -> None:
        row = await self.session.get(TelegramReportRow, period)
        if row is None:
            self.session.add(TelegramReportRow(period=period, last_sent_key=key, last_sent_at=now))
        else:
            row.last_sent_key = key
            row.last_sent_at = now
