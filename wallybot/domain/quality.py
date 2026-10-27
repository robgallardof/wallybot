"""Pure quality-result values. The stateful evaluation rule that produces them
(evaluate_series_quality) lives in wallybot/data/quality.py, a capability package -- domain
depends on nothing outward, so these value types live here, and RiskEngine (a domain port) can
depend on them without inverting the dependency direction.
"""

from dataclasses import dataclass
from enum import StrEnum

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
    # Public quality-status label, not a password.
    PASS = "PASS"  # nosec B105
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
