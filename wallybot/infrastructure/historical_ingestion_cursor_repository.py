from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.infrastructure.models import HistoricalIngestionCursorRow


class HistoricalIngestionCursorRepository:
    """Implements `market_ingestion.CursorStore` -- durable so a worker restart resumes from the
    last ingested candle instead of re-fetching (and re-writing) an already-published window."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def get(self, instrument_id: str, timeframe: str) -> datetime | None:
        async with self.sessions() as db:
            row = await db.scalar(
                select(HistoricalIngestionCursorRow).where(
                    HistoricalIngestionCursorRow.instrument_id == instrument_id,
                    HistoricalIngestionCursorRow.timeframe == timeframe,
                )
            )
            return row.last_close_time if row else None

    async def set(self, instrument_id: str, timeframe: str, last_close_time: datetime) -> None:
        async with self.sessions.begin() as db:
            # The `where` clause makes advancement monotonic even under an out-of-order or
            # concurrent call -- a cursor must never move backwards.
            await db.execute(
                insert(HistoricalIngestionCursorRow)
                .values(
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    last_close_time=last_close_time,
                )
                .on_conflict_do_update(
                    index_elements=["instrument_id", "timeframe"],
                    set_={"last_close_time": last_close_time},
                    where=HistoricalIngestionCursorRow.last_close_time < last_close_time,
                )
            )
