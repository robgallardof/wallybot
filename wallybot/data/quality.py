"""Stateful, cross-candle data quality gate.

Candle itself already enforces single-candle structural validity (finite positive prices,
nonnegative volume, low/high bounds) -- see wallybot/domain/market.py. This module checks what
only a *series* can reveal: ordering, duplicates, timestamp alignment, gaps, staleness, clock
drift and abnormal returns, per DATA.md's "Market quality and historical data" section.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.market import TIMEFRAME_DURATIONS, Candle

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

# Required-field gaps, staleness and failed synchronization are blocking per DATA.md; a warning
# is usable only when the explicit quality policy allows that reason. Ordering/duplicate/alignment
# issues mean the series itself cannot be trusted, so they block too -- only statistically notable
# but structurally sound signals (drift within a bound, an unusually large move) are warnings.
_BLOCKING_REASONS = frozenset(
    {
        "wrong_timeframe",
        "not_ordered",
        "duplicate_timestamps",
        "misaligned_timestamp",
        "gap_detected",
        "stale",
        "clock_drift_impossible",
    }
)
_WARNING_REASONS = frozenset({"clock_drift", "abnormal_return"})


class QualityStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAILURE = "FAILURE"


@dataclass(frozen=True)
class QualityIssue:
    reason: str
    evidence: str

    def __post_init__(self) -> None:
        if self.reason not in _BLOCKING_REASONS and self.reason not in _WARNING_REASONS:
            raise ValueError(f"Unknown quality reason code: {self.reason}")

    @property
    def severity(self) -> QualityStatus:
        if self.reason in _BLOCKING_REASONS:
            return QualityStatus.FAILURE
        return QualityStatus.WARNING


@dataclass(frozen=True)
class QualityReport:
    status: QualityStatus
    issues: tuple[QualityIssue, ...]


@dataclass(frozen=True)
class QualityPolicy:
    """Thresholds are versioned configuration per DATA.md, never a silent code change."""

    version: int
    timeframe: str
    max_stale_age: timedelta
    max_clock_drift: timedelta
    max_abnormal_return: Decimal

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.timeframe not in TIMEFRAME_DURATIONS:
            raise ValueError(f"Unsupported timeframe: {self.timeframe}")
        if self.max_stale_age <= timedelta(0):
            raise ValueError("max_stale_age must be positive")
        if self.max_clock_drift < timedelta(0):
            raise ValueError("max_clock_drift must be nonnegative")
        if self.max_abnormal_return <= 0:
            raise ValueError("max_abnormal_return must be positive")


def _check_ordering_and_duplicates(open_times: list[datetime]) -> list[QualityIssue]:
    issues = []
    if open_times != sorted(open_times):
        issues.append(QualityIssue("not_ordered", "candles are not sorted by open_time"))
    duplicate_count = len(open_times) - len(set(open_times))
    if duplicate_count:
        evidence = f"{duplicate_count} duplicate open_time value(s)"
        issues.append(QualityIssue("duplicate_timestamps", evidence))
    return issues


def _check_alignment_and_gaps(
    open_times: list[datetime], step: timedelta, timeframe: str
) -> list[QualityIssue]:
    issues = []
    misaligned = sum(1 for t in open_times if (t - _EPOCH) % step != timedelta(0))
    if misaligned:
        evidence = f"{misaligned} candle(s) not aligned to {timeframe} boundaries"
        issues.append(QualityIssue("misaligned_timestamp", evidence))
    unique_times = sorted(set(open_times))
    pairs = zip(unique_times, unique_times[1:], strict=False)
    gaps = sum(1 for earlier, later in pairs if later - earlier > step)
    if gaps:
        evidence = f"{gaps} gap(s) larger than one {timeframe} step"
        issues.append(QualityIssue("gap_detected", evidence))
    return issues


def _check_staleness_and_drift(
    candles: list[Candle], policy: QualityPolicy, now: datetime
) -> list[QualityIssue]:
    issues = []
    latest_close = max(c.close_time for c in candles)
    age = now - latest_close
    if age > policy.max_stale_age:
        evidence = f"latest candle is {age} old, exceeds {policy.max_stale_age}"
        issues.append(QualityIssue("stale", evidence))
    impossible_drift = sum(1 for c in candles if c.received_at < c.close_time)
    if impossible_drift:
        evidence = f"{impossible_drift} candle(s) received before they closed"
        issues.append(QualityIssue("clock_drift_impossible", evidence))
    else:
        max_drift = max((c.received_at - c.close_time for c in candles), default=timedelta(0))
        if max_drift > policy.max_clock_drift:
            evidence = f"max receipt delay {max_drift} exceeds {policy.max_clock_drift}"
            issues.append(QualityIssue("clock_drift", evidence))
    return issues


def _check_abnormal_returns(
    ordered: list[Candle], max_abnormal_return: Decimal
) -> list[QualityIssue]:
    abnormal = 0
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if earlier.close == 0:
            continue
        change = abs((later.close - earlier.close) / earlier.close)
        if change > max_abnormal_return:
            abnormal += 1
    if not abnormal:
        return []
    evidence = f"{abnormal} close-to-close move(s) exceed {max_abnormal_return}"
    return [QualityIssue("abnormal_return", evidence)]


def evaluate_series_quality(
    candles: list[Candle], policy: QualityPolicy, now: datetime
) -> QualityReport:
    if not candles:
        issue = QualityIssue("gap_detected", "no candles supplied")
        return QualityReport(status=QualityStatus.FAILURE, issues=(issue,))

    step = TIMEFRAME_DURATIONS[policy.timeframe]
    open_times = [c.open_time for c in candles]
    ordered = sorted(candles, key=lambda c: c.open_time)

    wrong_timeframe = sum(1 for c in candles if c.timeframe != policy.timeframe)
    issues: list[QualityIssue] = []
    if wrong_timeframe:
        evidence = f"{wrong_timeframe} candle(s) do not match policy timeframe {policy.timeframe}"
        issues.append(QualityIssue("wrong_timeframe", evidence))
    issues += _check_ordering_and_duplicates(open_times)
    issues += _check_alignment_and_gaps(open_times, step, policy.timeframe)
    issues += _check_staleness_and_drift(candles, policy, now)
    issues += _check_abnormal_returns(ordered, policy.max_abnormal_return)

    if not issues:
        status = QualityStatus.PASS
    elif any(issue.severity is QualityStatus.FAILURE for issue in issues):
        status = QualityStatus.FAILURE
    else:
        status = QualityStatus.WARNING
    return QualityReport(status=status, issues=tuple(issues))
