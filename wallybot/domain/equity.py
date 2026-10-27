"""Equity history: the daily/weekly loss, drawdown and high-water-mark inputs `RiskContext`
requires but this codebase had no producer for (`DecisionPipeline`'s own docstring: "there is no
equity or PnL tracker yet -- a caller supplies... whatever it currently knows").

RISK.md: "Persist boundaries and high-water marks so restarting cannot reset losses." Each
snapshot carries its own running `high_water_mark` (the max equity ever observed, including
itself), computed by `next_high_water_mark` from the immediately preceding snapshot -- so drawdown
never needs a full-history scan, only the latest snapshot. Daily/weekly loss do need a bounded
window of recent history (back to the day/week start boundary), never the full history.

This system has no deposit/withdrawal capability yet, so every equity change already comes only
from ledger-recorded trading activity -- RISK.md's "external cash flow" adjustment to day/week
starting equity has nothing to adjust for yet. Add it here only once such a capability exists, not
before (per AGENTS.md: "create modules when a real capability needs them").
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class EquitySnapshot:
    account_id: str
    environment: str
    equity: Decimal
    high_water_mark: Decimal
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.equity <= 0:
            raise ValueError("equity must be positive")
        if self.high_water_mark < self.equity:
            raise ValueError("high_water_mark cannot be below the equity it was recorded with")


def next_high_water_mark(previous: EquitySnapshot | None, equity: Decimal) -> Decimal:
    if previous is None:
        return equity
    return max(previous.high_water_mark, equity)


def compute_drawdown(current_equity: Decimal, high_water_mark: Decimal) -> Decimal:
    if high_water_mark <= 0:
        return Decimal(0)
    return max((high_water_mark - current_equity) / high_water_mark, Decimal(0))


def _start_of_utc_day(as_of: datetime) -> datetime:
    return as_of.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_utc_week(as_of: datetime) -> datetime:
    start_of_day = _start_of_utc_day(as_of)
    return start_of_day - timedelta(days=start_of_day.weekday())


def _starting_equity(history: tuple[EquitySnapshot, ...], boundary: datetime) -> Decimal | None:
    at_or_before = [snapshot for snapshot in history if snapshot.recorded_at <= boundary]
    if at_or_before:
        return max(at_or_before, key=lambda snapshot: snapshot.recorded_at).equity
    if history:
        # No snapshot exists as far back as the boundary (e.g. the account is younger than a
        # week) -- the earliest available snapshot is the most conservative honest baseline: it
        # never fabricates a loss that predates actually having any equity history.
        return min(history, key=lambda snapshot: snapshot.recorded_at).equity
    return None


def compute_daily_loss(
    history: tuple[EquitySnapshot, ...], current_equity: Decimal, as_of: datetime
) -> Decimal:
    starting = _starting_equity(history, _start_of_utc_day(as_of))
    if starting is None or starting <= 0:
        return Decimal(0)
    return max((starting - current_equity) / starting, Decimal(0))


def compute_weekly_loss(
    history: tuple[EquitySnapshot, ...], current_equity: Decimal, as_of: datetime
) -> Decimal:
    starting = _starting_equity(history, _start_of_utc_week(as_of))
    if starting is None or starting <= 0:
        return Decimal(0)
    return max((starting - current_equity) / starting, Decimal(0))
