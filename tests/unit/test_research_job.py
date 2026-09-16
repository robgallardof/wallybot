from datetime import UTC, datetime

import pytest

from wallybot.domain.research_job import (
    ResearchJob,
    ResearchJobStatus,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def pending() -> ResearchJob:
    return ResearchJob("job-1", "experiment-1", ResearchJobStatus.PENDING, NOW)


def test_research_job_happy_path_requires_artifact() -> None:
    running = pending().start(NOW)
    completed = running.complete(NOW, "research://artifacts/job-1.json")
    assert completed.status is ResearchJobStatus.COMPLETED


def test_cancelled_work_cannot_start_or_complete() -> None:
    cancelled = pending().request_cancellation().cancel(NOW)
    assert cancelled.status is ResearchJobStatus.CANCELLED
    with pytest.raises(ValueError):
        cancelled.start(NOW)


def test_running_job_with_cancel_request_cannot_complete() -> None:
    running = pending().start(NOW).request_cancellation()
    with pytest.raises(ValueError, match="non-cancelled"):
        running.complete(NOW, "research://artifacts/job-1.json")


def test_running_job_can_fail_with_a_reason() -> None:
    failed = pending().start(NOW).fail(NOW, "InsufficientHistoricalData: too few candles")
    assert failed.status is ResearchJobStatus.FAILED
    assert failed.failure_reason == "InsufficientHistoricalData: too few candles"


def test_pending_job_cannot_fail() -> None:
    with pytest.raises(ValueError, match="running"):
        pending().fail(NOW, "boom")


def test_fail_requires_a_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        pending().start(NOW).fail(NOW, "")
