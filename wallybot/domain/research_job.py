"""A constrained lifecycle for isolated research work.

Research jobs can produce artifacts and evidence, but this domain type intentionally contains no
promotion, control-state, exchange, or execution references.  A completed job is still only
research; a human-reviewed promotion is a separate future boundary.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from wallybot.domain.validation import require_aware_datetime


class ResearchJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ResearchJob:
    job_id: str
    experiment_id: str
    status: ResearchJobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancel_requested: bool = False
    artifact_uri: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.job_id or not self.experiment_id:
            raise ValueError("job_id and experiment_id are required")
        require_aware_datetime(self.created_at, "created_at")
        for name, value in (("started_at", self.started_at), ("completed_at", self.completed_at)):
            if value is not None:
                require_aware_datetime(value, name)

    def request_cancellation(self) -> "ResearchJob":
        terminal_statuses = {
            ResearchJobStatus.COMPLETED,
            ResearchJobStatus.FAILED,
            ResearchJobStatus.CANCELLED,
        }
        if self.status in terminal_statuses:
            raise ValueError("a terminal research job cannot be cancelled")
        return replace(self, cancel_requested=True)

    def start(self, at: datetime) -> "ResearchJob":
        require_aware_datetime(at, "at")
        if self.status is not ResearchJobStatus.PENDING or self.cancel_requested:
            raise ValueError("only a non-cancelled pending research job can start")
        return replace(self, status=ResearchJobStatus.RUNNING, started_at=at)

    def complete(self, at: datetime, artifact_uri: str) -> "ResearchJob":
        require_aware_datetime(at, "at")
        if self.status is not ResearchJobStatus.RUNNING or self.cancel_requested:
            raise ValueError("only a running non-cancelled research job can complete")
        if not artifact_uri:
            raise ValueError("a completed research job requires an artifact_uri")
        return replace(
            self,
            status=ResearchJobStatus.COMPLETED,
            completed_at=at,
            artifact_uri=artifact_uri,
        )

    def cancel(self, at: datetime) -> "ResearchJob":
        require_aware_datetime(at, "at")
        if self.status not in {ResearchJobStatus.PENDING, ResearchJobStatus.RUNNING}:
            raise ValueError("only pending or running research jobs can be cancelled")
        return replace(
            self,
            status=ResearchJobStatus.CANCELLED,
            completed_at=at,
            cancel_requested=True,
        )

    def fail(self, at: datetime, reason: str) -> "ResearchJob":
        require_aware_datetime(at, "at")
        if self.status is not ResearchJobStatus.RUNNING:
            raise ValueError("only a running research job can fail")
        if not reason:
            raise ValueError("a failed research job requires a reason")
        return replace(
            self,
            status=ResearchJobStatus.FAILED,
            completed_at=at,
            failure_reason=reason,
        )
