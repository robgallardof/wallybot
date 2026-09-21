"""Persistent circuit breakers: a latched trip state, distinct from a per-tick threshold check.

RISK.md: "Persist latch/reason/time. Recovery requires healthy evidence; hard loss/drawdown,
ambiguity and reconciliation breakers require operator acknowledgment with fresh MFA. A scheduler
cannot silently reset a breaker at midnight." This is a real distinction from
`wallybot.domain.equity`'s daily/weekly loss, which is *correctly* a fresh per-day/per-week
computation (a new day gets a fresh loss budget, by definition) -- but the breaker that trips when
that budget is breached must stay tripped across a day boundary until an operator clears it, never
silently re-arm itself just because the underlying metric happened to recompute back under the
limit.

Only the daily/weekly loss, drawdown and reconciliation breakers are modeled here -- RISK.md's
fuller taxonomy (stale data, abnormal spread/volatility, exchange outages, repeated execution
errors, unknown orders, mismatches, DB failure, clock drift) needs trigger wiring from parts of
the system this slice does not touch; not fabricated as "no other breaker types exist."

This system has one account, so a breaker is modeled as a single latched state per `BreakerType`
rather than a log of instances -- `trip` is idempotent (a repeated trip while already tripped
keeps the original reason/time, never overwritten by a later one) and `clear` requires the breaker
to currently be tripped.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.risk import RiskPolicy


class BreakerType(StrEnum):
    DAILY_LOSS = "DAILY_LOSS"
    WEEKLY_LOSS = "WEEKLY_LOSS"
    DRAWDOWN = "DRAWDOWN"
    RECONCILIATION = "RECONCILIATION"


@dataclass(frozen=True)
class Breaker:
    breaker_type: BreakerType
    reason: str
    tripped_at: datetime
    cleared_at: datetime | None = None
    cleared_by: str | None = None

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("reason is required")
        if self.cleared_at is not None and self.cleared_at < self.tripped_at:
            raise ValueError("cleared_at cannot be before tripped_at")

    @property
    def active(self) -> bool:
        return self.cleared_at is None


def breakers_to_trip(
    daily_loss: Decimal,
    weekly_loss: Decimal,
    drawdown: Decimal,
    policy: RiskPolicy,
    reconciliation_healthy: bool,
) -> tuple[tuple[BreakerType, str], ...]:
    """What should be tripped given this tick's fresh metrics -- the caller (a repository) decides
    whether each is a genuinely new trip or a no-op against an already-active one."""
    trips: list[tuple[BreakerType, str]] = []
    if daily_loss >= policy.max_daily_loss:
        trips.append(
            (
                BreakerType.DAILY_LOSS,
                f"daily loss {daily_loss} at or beyond limit {policy.max_daily_loss}",
            )
        )
    if weekly_loss >= policy.max_weekly_loss:
        trips.append(
            (
                BreakerType.WEEKLY_LOSS,
                f"weekly loss {weekly_loss} at or beyond limit {policy.max_weekly_loss}",
            )
        )
    if drawdown >= policy.max_drawdown:
        trips.append(
            (BreakerType.DRAWDOWN, f"drawdown {drawdown} at or beyond limit {policy.max_drawdown}")
        )
    if not reconciliation_healthy:
        trips.append(
            (BreakerType.RECONCILIATION, "reconciliation reported at least one unresolved error")
        )
    return tuple(trips)
