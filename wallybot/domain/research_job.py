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
    """Lifecycle state of a :class:`ResearchJob`.

    :cvar PENDING: Enqueued, not yet claimed by a worker.
    :cvar RUNNING: Claimed; a worker is executing it.
    :cvar CANCELLED: Stopped before or during execution, via :meth:`ResearchJob.cancel`.
    :cvar COMPLETED: Finished successfully; ``artifact_uri`` is set.
    :cvar FAILED: Finished with an error; ``failure_reason`` is set.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ResearchJob:
    """An isolated unit of research work tied to one experiment.

    Immutable: every state transition (:meth:`start`, :meth:`complete`, :meth:`cancel`,
    :meth:`fail`) returns a new instance rather than mutating this one.

    :ivar job_id: Stable identifier for this job.
    :ivar experiment_id: The ``experiment_records`` row this job operates on.
    :ivar status: Current lifecycle state; see :class:`ResearchJobStatus`.
    :ivar created_at: When the job was enqueued (aware UTC).
    :ivar started_at: When it began running, if it has (aware UTC).
    :ivar completed_at: When it reached a terminal state, if it has (aware UTC).
    :ivar cancel_requested: Whether cancellation was requested; a running job with this set can
        still only reach :attr:`ResearchJobStatus.CANCELLED`, never ``COMPLETED``.
    :ivar artifact_uri: Set only on successful completion.
    :ivar failure_reason: Set only on failure.
    :raises ValueError: If ``job_id``/``experiment_id`` is empty, or any datetime field is naive.
    """

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
        """Flag this job to stop at the next opportunity.

        :returns: A copy with ``cancel_requested=True``. Status is unchanged here; a
            :attr:`~ResearchJobStatus.PENDING` job is cancelled outright by the repository layer,
            while a :attr:`~ResearchJobStatus.RUNNING` one only stops once the worker notices.
        :raises ValueError: If the job is already in a terminal state.
        """
        terminal_statuses = {
            ResearchJobStatus.COMPLETED,
            ResearchJobStatus.FAILED,
            ResearchJobStatus.CANCELLED,
        }
        if self.status in terminal_statuses:
            raise ValueError("a terminal research job cannot be cancelled")
        return replace(self, cancel_requested=True)

    def start(self, at: datetime) -> "ResearchJob":
        """Transition ``PENDING`` -> ``RUNNING``.

        :param at: Aware UTC timestamp to record as :attr:`started_at`.
        :returns: A copy with :attr:`status` set to :attr:`~ResearchJobStatus.RUNNING`.
        :raises ValueError: If the job is not pending, or cancellation was already requested.
        """
        require_aware_datetime(at, "at")
        if self.status is not ResearchJobStatus.PENDING or self.cancel_requested:
            raise ValueError("only a non-cancelled pending research job can start")
        return replace(self, status=ResearchJobStatus.RUNNING, started_at=at)

    def complete(self, at: datetime, artifact_uri: str) -> "ResearchJob":
        """Transition ``RUNNING`` -> ``COMPLETED``.

        :param at: Aware UTC timestamp to record as :attr:`completed_at`.
        :param artifact_uri: Non-empty reference to the produced result (this codebase points it
            at the new ``experiment_id`` a re-run produced).
        :returns: A copy with :attr:`status` set to :attr:`~ResearchJobStatus.COMPLETED`.
        :raises ValueError: If the job is not running, cancellation was requested, or
            ``artifact_uri`` is empty.
        """
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
        """Transition ``PENDING``/``RUNNING`` -> ``CANCELLED``.

        :param at: Aware UTC timestamp to record as :attr:`completed_at`.
        :returns: A copy with :attr:`status` set to :attr:`~ResearchJobStatus.CANCELLED`.
        :raises ValueError: If the job is already in a terminal state.
        """
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
        """Transition ``RUNNING`` -> ``FAILED``.

        :param at: Aware UTC timestamp to record as :attr:`completed_at`.
        :param reason: Non-empty, human-readable explanation of the failure.
        :returns: A copy with :attr:`status` set to :attr:`~ResearchJobStatus.FAILED`.
        :raises ValueError: If the job is not running, or ``reason`` is empty.
        """
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
