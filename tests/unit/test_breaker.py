from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.breaker import Breaker, BreakerType, breakers_to_trip
from wallybot.domain.risk import RiskPolicy

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)
POLICY = RiskPolicy(
    version=1,
    max_daily_loss=Decimal("0.02"),
    max_weekly_loss=Decimal("0.05"),
    max_drawdown=Decimal("0.10"),
    max_spread_ratio=Decimal("0.01"),
)


def test_breaker_requires_a_reason():
    with pytest.raises(ValueError):
        Breaker(breaker_type=BreakerType.DAILY_LOSS, reason="", tripped_at=AS_OF)


def test_breaker_cleared_at_cannot_precede_tripped_at():
    with pytest.raises(ValueError):
        Breaker(
            breaker_type=BreakerType.DAILY_LOSS,
            reason="x",
            tripped_at=AS_OF,
            cleared_at=AS_OF - timedelta(hours=1),
        )


def test_a_breaker_with_no_cleared_at_is_active():
    breaker = Breaker(breaker_type=BreakerType.DAILY_LOSS, reason="x", tripped_at=AS_OF)
    assert breaker.active is True


def test_a_cleared_breaker_is_not_active():
    breaker = Breaker(
        breaker_type=BreakerType.DAILY_LOSS,
        reason="x",
        tripped_at=AS_OF,
        cleared_at=AS_OF + timedelta(minutes=1),
        cleared_by="admin-1",
    )
    assert breaker.active is False


def test_no_trips_when_everything_is_within_limits():
    trips = breakers_to_trip(
        daily_loss=Decimal("0.01"),
        weekly_loss=Decimal("0.02"),
        drawdown=Decimal("0.05"),
        policy=POLICY,
        reconciliation_healthy=True,
    )
    assert trips == ()


def test_daily_loss_at_exact_limit_trips():
    # "Equality at a limit triggers the breaker" -- RISK.md, same convention the risk engine uses.
    trips = breakers_to_trip(
        daily_loss=Decimal("0.02"),
        weekly_loss=Decimal("0"),
        drawdown=Decimal("0"),
        policy=POLICY,
        reconciliation_healthy=True,
    )
    assert len(trips) == 1
    assert trips[0][0] is BreakerType.DAILY_LOSS
    assert "daily loss" in trips[0][1]


def test_weekly_loss_beyond_limit_trips():
    trips = breakers_to_trip(
        daily_loss=Decimal("0"),
        weekly_loss=Decimal("0.06"),
        drawdown=Decimal("0"),
        policy=POLICY,
        reconciliation_healthy=True,
    )
    assert [t[0] for t in trips] == [BreakerType.WEEKLY_LOSS]


def test_drawdown_beyond_limit_trips():
    trips = breakers_to_trip(
        daily_loss=Decimal("0"),
        weekly_loss=Decimal("0"),
        drawdown=Decimal("0.15"),
        policy=POLICY,
        reconciliation_healthy=True,
    )
    assert [t[0] for t in trips] == [BreakerType.DRAWDOWN]


def test_unhealthy_reconciliation_trips():
    trips = breakers_to_trip(
        daily_loss=Decimal("0"),
        weekly_loss=Decimal("0"),
        drawdown=Decimal("0"),
        policy=POLICY,
        reconciliation_healthy=False,
    )
    assert [t[0] for t in trips] == [BreakerType.RECONCILIATION]


def test_multiple_simultaneous_breaches_all_trip():
    trips = breakers_to_trip(
        daily_loss=Decimal("0.03"),
        weekly_loss=Decimal("0.06"),
        drawdown=Decimal("0.20"),
        policy=POLICY,
        reconciliation_healthy=False,
    )
    assert {t[0] for t in trips} == {
        BreakerType.DAILY_LOSS,
        BreakerType.WEEKLY_LOSS,
        BreakerType.DRAWDOWN,
        BreakerType.RECONCILIATION,
    }
