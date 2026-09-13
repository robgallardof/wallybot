from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.domain.control import Status
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.portfolio import AllocationProposal, Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityIssue, QualityReport, QualityStatus
from wallybot.domain.risk import ExchangeStatus, RiskContext, RiskDecision, RiskPolicy
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine

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

POLICY = RiskPolicy(
    version=1,
    max_daily_loss=Decimal("0.02"),
    max_weekly_loss=Decimal("0.05"),
    max_drawdown=Decimal("0.10"),
    max_spread_ratio=Decimal("0.01"),
)
PORTFOLIO_POLICY = PortfolioPolicy(
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
ENGINE = DeterministicRiskEngine()


def make_proposal(**overrides) -> AllocationProposal:
    fields = {
        "instrument": INSTRUMENT,
        "bucket": Bucket.CORE,
        "version": 1,
        "as_of": AS_OF,
        "proposed_notional": Decimal("1000"),
        "approved": True,
        "reasons": (),
    }
    fields.update(overrides)
    return AllocationProposal(**fields)


def make_snapshot(bid: str = "99.99", ask: str = "100.01") -> MarketSnapshot:
    return MarketSnapshot(
        instrument=INSTRUMENT, bid=Decimal(bid), ask=Decimal(ask), timestamp=AS_OF, source="fake"
    )


def make_context(**overrides) -> RiskContext:
    fields = {
        "control_status": Status.RUNNING,
        "portfolio_state": PortfolioState(
            equity=Decimal("10000"), bucket_exposure={}, asset_exposure={}, open_positions=0
        ),
        "portfolio_policy": PORTFOLIO_POLICY,
        "quality": QualityReport(status=QualityStatus.PASS, issues=()),
        "snapshot": make_snapshot(),
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


def test_clean_approval():
    assessment = ENGINE.evaluate(make_proposal(), make_context(), POLICY)
    assert assessment.decision == RiskDecision.APPROVED
    assert assessment.final_notional == Decimal("1000")


def test_unapproved_proposal_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(approved=False, proposed_notional=Decimal("0"), reasons=("x",)),
        make_context(),
        POLICY,
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "not approved" in assessment.reasons[0]


def test_control_not_running_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(control_status=Status.PAUSED), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "RUNNING" in assessment.reasons[0]


def test_quality_failure_is_rejected():
    quality = QualityReport(
        status=QualityStatus.FAILURE, issues=(QualityIssue("stale", "too old"),)
    )
    assessment = ENGINE.evaluate(make_proposal(), make_context(quality=quality), POLICY)
    assert assessment.decision == RiskDecision.REJECTED
    assert "quality" in assessment.reasons[0]


def test_quality_warning_is_not_rejected():
    quality = QualityReport(
        status=QualityStatus.WARNING, issues=(QualityIssue("abnormal_return", "big move"),)
    )
    assessment = ENGINE.evaluate(make_proposal(), make_context(quality=quality), POLICY)
    assert assessment.decision == RiskDecision.APPROVED


def test_exchange_not_healthy_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(),
        make_context(exchange_status=ExchangeStatus.DEGRADED),
        POLICY,
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "exchange" in assessment.reasons[0]


def test_reconciliation_unhealthy_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(reconciliation_healthy=False), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "reconciliation" in assessment.reasons[0]


def test_active_breaker_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(active_breakers=frozenset({"STALE_DATA"})), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "STALE_DATA" in assessment.reasons[0]


def test_daily_loss_at_exact_limit_is_rejected():
    # "Equality at a limit triggers the breaker" -- RISK.md.
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(daily_loss=Decimal("0.02")), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "daily loss" in assessment.reasons[0]


def test_weekly_loss_at_exact_limit_is_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(weekly_loss=Decimal("0.05")), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED


def test_drawdown_at_exact_limit_is_rejected():
    assessment = ENGINE.evaluate(make_proposal(), make_context(drawdown=Decimal("0.10")), POLICY)
    assert assessment.decision == RiskDecision.REJECTED


def test_loss_just_below_limit_is_not_rejected():
    assessment = ENGINE.evaluate(
        make_proposal(), make_context(daily_loss=Decimal("0.0199")), POLICY
    )
    assert assessment.decision == RiskDecision.APPROVED


def test_spread_beyond_limit_is_rejected():
    wide_spread = make_snapshot(bid="95", ask="100")  # 5% spread, limit is 1%
    assessment = ENGINE.evaluate(make_proposal(), make_context(snapshot=wide_spread), POLICY)
    assert assessment.decision == RiskDecision.REJECTED
    assert "spread" in assessment.reasons[0]


def test_capacity_shortfall_reduces_size():
    state = PortfolioState(
        equity=Decimal("10000"),
        bucket_exposure={Bucket.CORE: Decimal("6500")},
        asset_exposure={},
        open_positions=0,
    )
    assessment = ENGINE.evaluate(make_proposal(), make_context(portfolio_state=state), POLICY)
    assert assessment.decision == RiskDecision.APPROVED_WITH_REDUCED_SIZE
    assert assessment.final_notional == Decimal("500")


def test_no_remaining_capacity_is_rejected():
    state = PortfolioState(
        equity=Decimal("10000"),
        bucket_exposure={Bucket.CORE: Decimal("7000")},
        asset_exposure={},
        open_positions=0,
    )
    assessment = ENGINE.evaluate(make_proposal(), make_context(portfolio_state=state), POLICY)
    assert assessment.decision == RiskDecision.REJECTED
    assert "capacity" in assessment.reasons[0]


def test_instrument_precision_reduces_size():
    coarse_instrument = Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base="XYZ",
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.01"),
        min_quantity=Decimal("0.01"),
    )
    snapshot = MarketSnapshot(
        instrument=coarse_instrument,
        bid=Decimal("299.99"),
        ask=Decimal("300.02"),
        timestamp=AS_OF,
        source="fake",
    )
    proposal = make_proposal(instrument=coarse_instrument, proposed_notional=Decimal("1000"))
    assessment = ENGINE.evaluate(proposal, make_context(snapshot=snapshot), POLICY)
    assert assessment.decision == RiskDecision.APPROVED_WITH_REDUCED_SIZE
    assert assessment.final_notional < Decimal("1000")
    assert "rounded down" in assessment.reasons[0]


def test_quantity_below_minimum_is_rejected_as_zero_sized():
    assessment = ENGINE.evaluate(
        make_proposal(proposed_notional=Decimal("0.005")), make_context(), POLICY
    )
    assert assessment.decision == RiskDecision.REJECTED
    assert "minimum" in assessment.reasons[0]


def test_speculative_bucket_capped_by_single_asset_ceiling():
    proposal = make_proposal(bucket=Bucket.SPECULATIVE, proposed_notional=Decimal("5000"))
    assessment = ENGINE.evaluate(proposal, make_context(), POLICY)
    assert assessment.decision == RiskDecision.APPROVED_WITH_REDUCED_SIZE
    # single speculative asset cap = 3% of 10000 = 300
    assert assessment.final_notional == Decimal("300")
