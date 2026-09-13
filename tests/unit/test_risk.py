from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.control import Status
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.portfolio import Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityReport, QualityStatus
from wallybot.domain.risk import (
    ExchangeStatus,
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskPolicy,
)

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def make_policy(**overrides) -> RiskPolicy:
    fields = {
        "version": 1,
        "max_daily_loss": Decimal("0.02"),
        "max_weekly_loss": Decimal("0.05"),
        "max_drawdown": Decimal("0.10"),
        "max_spread_ratio": Decimal("0.01"),
    }
    fields.update(overrides)
    return RiskPolicy(**fields)


def make_portfolio_policy() -> PortfolioPolicy:
    return PortfolioPolicy(
        version=1,
        bucket_targets={
            Bucket.CORE: Decimal("0.70"),
            Bucket.GROWTH: Decimal("0.20"),
            Bucket.SPECULATIVE: Decimal("0.10"),
        },
        speculative_operating_max=Decimal("0.10"),
        speculative_absolute_max=Decimal("0.15"),
        single_speculative_asset_max=Decimal("0.03"),
        max_open_positions=1,
    )


def make_context(**overrides) -> RiskContext:
    fields = {
        "control_status": Status.RUNNING,
        "portfolio_state": PortfolioState(
            equity=Decimal("10000"), bucket_exposure={}, asset_exposure={}, open_positions=0
        ),
        "portfolio_policy": make_portfolio_policy(),
        "quality": QualityReport(status=QualityStatus.PASS, issues=()),
        "snapshot": MarketSnapshot(
            instrument=INSTRUMENT,
            bid=Decimal("99.99"),
            ask=Decimal("100.01"),
            timestamp=AS_OF,
            source="fake",
        ),
        "exchange_status": ExchangeStatus.HEALTHY,
        "reconciliation_healthy": True,
        "active_breakers": frozenset(),
        "daily_loss": Decimal("0"),
        "weekly_loss": Decimal("0"),
        "drawdown": Decimal("0"),
        "as_of": AS_OF,
        "expiry": timedelta(minutes=5),
    }
    fields.update(overrides)
    return RiskContext(**fields)


def test_accepts_risk_md_initial_policy():
    assert make_policy().max_daily_loss == Decimal("0.02")


def test_rejects_zero_max_daily_loss():
    with pytest.raises(ValueError):
        make_policy(max_daily_loss=Decimal("0"))


def test_rejects_max_daily_loss_above_one():
    with pytest.raises(ValueError):
        make_policy(max_daily_loss=Decimal("1.5"))


def test_context_rejects_nonpositive_expiry():
    with pytest.raises(ValueError):
        make_context(expiry=timedelta(0))


def test_context_rejects_negative_loss():
    with pytest.raises(ValueError):
        make_context(daily_loss=Decimal("-0.01"))


def test_assessment_rejected_must_have_zero_notional():
    with pytest.raises(ValueError):
        RiskAssessment(
            decision=RiskDecision.REJECTED,
            final_notional=Decimal("1"),
            final_quantity=Decimal("1"),
            version=1,
            as_of=AS_OF,
            expires_at=AS_OF + timedelta(minutes=1),
            reasons=("x",),
        )


def test_assessment_approved_must_have_positive_notional():
    with pytest.raises(ValueError):
        RiskAssessment(
            decision=RiskDecision.APPROVED,
            final_notional=Decimal("0"),
            final_quantity=Decimal("0"),
            version=1,
            as_of=AS_OF,
            expires_at=AS_OF + timedelta(minutes=1),
            reasons=("x",),
        )


def test_assessment_requires_at_least_one_reason():
    with pytest.raises(ValueError):
        RiskAssessment(
            decision=RiskDecision.APPROVED,
            final_notional=Decimal("1"),
            final_quantity=Decimal("1"),
            version=1,
            as_of=AS_OF,
            expires_at=AS_OF + timedelta(minutes=1),
            reasons=(),
        )


def test_assessment_expiry_must_be_after_as_of():
    with pytest.raises(ValueError):
        RiskAssessment(
            decision=RiskDecision.APPROVED,
            final_notional=Decimal("1"),
            final_quantity=Decimal("1"),
            version=1,
            as_of=AS_OF,
            expires_at=AS_OF,
            reasons=("x",),
        )
