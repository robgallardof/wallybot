"""PostgreSQL queue for isolated research work; deliberately unrelated to execution jobs."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.research_job import ResearchJob, ResearchJobStatus
from wallybot.infrastructure.models import JobRow

_KIND = "RESEARCH"


class ResearchJobRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def enqueue(self, job: ResearchJob, payload: dict[str, str]) -> None:
        async with self.sessions.begin() as db:
            db.add(
                JobRow(
                    id=job.job_id,
                    kind=_KIND,
                    scheduled_at=int(job.created_at.timestamp()),
                    status=job.status.value,
                    attempts=0,
                    payload={"experiment_id": job.experiment_id, **payload},
                    cancel_requested=job.cancel_requested,
                )
            )

    async def claim_next(self, now: int) -> JobRow | None:
        async with self.sessions.begin() as db:
            row = await db.scalar(
                select(JobRow)
                .where(
                    JobRow.kind == _KIND,
                    JobRow.status == ResearchJobStatus.PENDING.value,
                    JobRow.scheduled_at <= now,
                    JobRow.cancel_requested.is_(False),
                )
                .order_by(JobRow.scheduled_at, JobRow.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return None
            row.status = ResearchJobStatus.RUNNING.value
            row.claimed_at = now
            row.attempts += 1
            return row

    async def request_cancellation(self, job_id: str, now: int) -> bool:
        async with self.sessions.begin() as db:
            row = await db.get(JobRow, job_id, with_for_update=True)
            terminal_statuses = {"COMPLETED", "FAILED", "CANCELLED"}
            if row is None or row.kind != _KIND or row.status in terminal_statuses:
                return False
            row.cancel_requested = True
            if row.status == ResearchJobStatus.PENDING.value:
                row.status = ResearchJobStatus.CANCELLED.value
                row.completed_at = now
            return True

    async def complete(self, job_id: str, now: int, artifact_uri: str) -> bool:
        async with self.sessions.begin() as db:
            row = await db.get(JobRow, job_id, with_for_update=True)
            if row is None or row.kind != _KIND or row.status != ResearchJobStatus.RUNNING.value:
                return False
            if row.cancel_requested:
                row.status = ResearchJobStatus.CANCELLED.value
            else:
                row.status = ResearchJobStatus.COMPLETED.value
                row.artifact_uri = artifact_uri
            row.completed_at = now
            return True

    async def fail(self, job_id: str, now: int, error: str) -> bool:
        async with self.sessions.begin() as db:
            row = await db.get(JobRow, job_id, with_for_update=True)
            if row is None or row.kind != _KIND or row.status != ResearchJobStatus.RUNNING.value:
                return False
            row.status = (
                ResearchJobStatus.CANCELLED.value
                if row.cancel_requested
                else ResearchJobStatus.FAILED.value
            )
            row.error = error
            row.completed_at = now
            return True

    async def get(self, job_id: str) -> JobRow | None:
        async with self.sessions() as db:
            row = await db.get(JobRow, job_id)
            return row if row is not None and row.kind == _KIND else None

    async def list_recent(self, limit: int = 100) -> tuple[JobRow, ...]:
        async with self.sessions() as db:
            rows = (
                await db.scalars(
                    select(JobRow)
                    .where(JobRow.kind == _KIND)
                    .order_by(JobRow.scheduled_at.desc(), JobRow.id.desc())
                    .limit(limit)
                )
            ).all()
            return tuple(rows)
