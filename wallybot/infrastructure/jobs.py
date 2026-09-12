from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.infrastructure.models import ChallengeRow, HeartbeatRow, JobRow, SessionRow


async def tick(service: str, sessions: async_sessionmaker[AsyncSession], now: int) -> None:
    """Durable heartbeat and bounded DB-only maintenance, committed atomically."""
    async with sessions.begin() as db:
        await db.execute(
            insert(HeartbeatRow)
            .values(service=service, timestamp=now)
            .on_conflict_do_update(index_elements=[HeartbeatRow.service], set_={"timestamp": now})
        )
        if service == "scheduler":
            await db.execute(
                insert(JobRow)
                .values(
                    id=f"cleanup:{now // 60}",
                    kind="CLEANUP",
                    scheduled_at=now,
                    status="PENDING",
                    attempts=0,
                )
                .on_conflict_do_nothing()
            )
        if service == "worker":
            job = await db.scalar(
                select(JobRow)
                .where(
                    JobRow.status == "PENDING", JobRow.kind == "CLEANUP", JobRow.scheduled_at <= now
                )
                .order_by(JobRow.scheduled_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if job:
                await db.execute(delete(ChallengeRow).where(ChallengeRow.expires_at <= now))
                await db.execute(delete(SessionRow).where(SessionRow.expires_at <= now))
                job.status, job.attempts = "DONE", job.attempts + 1
                await db.execute(
                    delete(JobRow).where(JobRow.status == "DONE", JobRow.scheduled_at < now - 86400)
                )
