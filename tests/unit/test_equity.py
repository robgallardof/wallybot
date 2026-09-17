from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.equity import (
    EquitySnapshot,
    compute_daily_loss,
    compute_drawdown,
    compute_weekly_loss,
    next_high_water_mark,
)

ACCOUNT = "paper:test-user"


def snap(equity: str, hwm: str, at: datetime) -> EquitySnapshot:
    return EquitySnapshot(
        account_id=ACCOUNT,
        environment="PAPER",
        equity=Decimal(equity),
        high_water_mark=Decimal(hwm),
        recorded_at=at,
    )


def test_equity_must_be_positive():
    with pytest.raises(ValueError):
        EquitySnapshot(
            account_id=ACCOUNT,
            environment="PAPER",
            equity=Decimal("0"),
            high_water_mark=Decimal("100"),
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_high_water_mark_cannot_be_below_equity():
    with pytest.raises(ValueError):
        EquitySnapshot(
            account_id=ACCOUNT,
            environment="PAPER",
            equity=Decimal("200"),
            high_water_mark=Decimal("100"),
            recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_next_high_water_mark_with_no_prior_snapshot_is_the_equity_itself():
    assert next_high_water_mark(None, Decimal("1000")) == Decimal("1000")


def test_next_high_water_mark_tracks_the_running_maximum():
    previous = snap("1200", "1500", datetime(2026, 1, 1, tzinfo=UTC))
    assert next_high_water_mark(previous, Decimal("1000")) == Decimal("1500")
    assert next_high_water_mark(previous, Decimal("1600")) == Decimal("1600")


def test_drawdown_from_high_water_mark():
    assert compute_drawdown(Decimal("900"), Decimal("1000")) == Decimal("0.1")


def test_drawdown_is_never_negative_when_at_a_new_high():
    assert compute_drawdown(Decimal("1100"), Decimal("1000")) == Decimal("0")


def test_daily_loss_with_no_history_is_zero():
    assert compute_daily_loss((), Decimal("1000"), datetime(2026, 1, 1, tzinfo=UTC)) == Decimal(0)


def test_daily_loss_uses_the_snapshot_at_or_before_todays_utc_midnight():
    history = (
        snap("1000", "1000", datetime(2025, 12, 31, 23, 0, tzinfo=UTC)),
        snap("990", "1000", datetime(2026, 1, 1, 1, 0, tzinfo=UTC)),
    )
    as_of = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    # Baseline is the 23:00 (Dec 31) snapshot, the latest one at-or-before today's UTC midnight.
    assert compute_daily_loss(history, Decimal("950"), as_of) == Decimal("0.05")


def test_daily_loss_falls_back_to_earliest_snapshot_when_none_predates_the_boundary():
    history = (snap("1000", "1000", datetime(2026, 1, 1, 6, 0, tzinfo=UTC)),)
    as_of = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert compute_daily_loss(history, Decimal("900"), as_of) == Decimal("0.1")


def test_daily_loss_is_never_negative_on_a_gain():
    history = (snap("1000", "1000", datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),)
    as_of = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert compute_daily_loss(history, Decimal("1100"), as_of) == Decimal("0")


def test_weekly_loss_uses_monday_utc_start():
    # 2026-01-05 is a Monday.
    history = (snap("2000", "2000", datetime(2026, 1, 5, 0, 0, tzinfo=UTC)),)
    as_of = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)  # Thursday same week
    assert compute_weekly_loss(history, Decimal("1900"), as_of) == Decimal("0.05")


def test_weekly_loss_carries_forward_the_last_snapshot_before_the_boundary():
    # No snapshot lands exactly at Monday 00:00 -- the last one recorded before it (Friday, a
    # carried-forward "opening balance" for the week, same as day-over-day accounting) is the
    # correct baseline, not the next snapshot recorded hours into Monday.
    history = (
        snap("2400", "2400", datetime(2026, 1, 2, 0, 0, tzinfo=UTC)),  # previous week (Friday)
        snap("2000", "2400", datetime(2026, 1, 5, 1, 0, tzinfo=UTC)),  # a later Monday reading
    )
    as_of = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)
    assert compute_weekly_loss(history, Decimal("1900"), as_of) == Decimal("500") / Decimal("2400")
