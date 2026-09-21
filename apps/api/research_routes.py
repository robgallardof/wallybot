"""Authenticated management surface for isolated, non-trading research jobs."""

import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import ResearchJobListView, ResearchJobView
from apps.api.schemas import ResearchJobCreate
from wallybot.domain.research_job import ResearchJob, ResearchJobStatus
from wallybot.infrastructure.research_job_repository import ResearchJobRepository

router = APIRouter(prefix="/api/research/jobs", tags=["research"])

# A simple system-wide quota (PENDING.md Fase 7's "cuotas") -- this system has one admin account,
# not per-user tenancy, so the queue depth is the only quota that makes sense here. Bounds runaway
# enqueueing, not a claim about how much load research_worker can actually handle concurrently
# (it claims and runs one job at a time, per `run_pending_research_job`).
MAX_ACTIVE_RESEARCH_JOBS = 5


def _view(row) -> ResearchJobView:
    return ResearchJobView(
        id=row.id,
        experiment_id=row.payload["experiment_id"],
        purpose=row.payload["purpose"],
        status=row.status,
        attempts=row.attempts,
        cancel_requested=row.cancel_requested,
        artifact_uri=row.artifact_uri,
        error=row.error,
        created_at=row.scheduled_at,
        claimed_at=row.claimed_at,
        completed_at=row.completed_at,
    )


@router.post("", response_model=ResearchJobView)
async def create_research_job(
    body: ResearchJobCreate, request: Request, user: Admin
) -> ResearchJobView:
    repository = ResearchJobRepository(request.app.state.sessions)
    if await repository.count_active() >= MAX_ACTIVE_RESEARCH_JOBS:
        raise HTTPException(
            status_code=429,
            detail="Too many active research jobs -- wait for one to finish or cancel one first",
        )

    now = int(time.time())
    job = ResearchJob(
        job_id=str(uuid4()),
        experiment_id=body.experiment_id,
        status=ResearchJobStatus.PENDING,
        created_at=datetime.fromtimestamp(now, UTC),
    )
    await repository.enqueue(job, {"purpose": body.purpose})
    row = await repository.get(job.job_id)
    if row is None:
        raise HTTPException(status_code=503, detail="Research job was not persisted")
    return _view(row)


@router.get("", response_model=ResearchJobListView)
async def list_research_jobs(request: Request, user: SignedIn) -> ResearchJobListView:
    rows = await ResearchJobRepository(request.app.state.sessions).list_recent()
    return ResearchJobListView(rows=[_view(row) for row in rows])


@router.delete("/{job_id}", response_model=ResearchJobView)
async def cancel_research_job(job_id: str, request: Request, user: Admin) -> ResearchJobView:
    repository = ResearchJobRepository(request.app.state.sessions)
    if not await repository.request_cancellation(job_id, int(time.time())):
        raise HTTPException(
            status_code=404,
            detail="Research job is unavailable or already terminal",
        )
    row = await repository.get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return _view(row)
