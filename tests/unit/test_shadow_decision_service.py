from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.application.shadow_decision_service import ShadowDecisionService
from wallybot.domain.control import Status
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.portfolio import Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityReport, QualityStatus
from wallybot.domain.risk import ExchangeStatus, RiskContext, RiskDecision, RiskPolicy
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
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
    max_open_positions=5,
)
RISK_POLICY = RiskPolicy(
    version=1,
    max_daily_loss=Decimal("0.02"),
    max_weekly_loss=Decimal("0.05"),
    max_drawdown=Decimal("0.10"),
    max_spread_ratio=Decimal("0.01"),
)


def make_proposal(**overrides) -> TradeProposal:
    fields: dict[str, object] = {
        "proposal_id": "prop-1",
        "instrument": INSTRUMENT,
        "direction": TradeDirection.LONG,
        "strategy_id": "ai-v1",
        "confidence": Decimal("0.8"),
        "suggested_allocation_pct": Decimal("0.05"),
        "entry_price": Decimal("50000"),
        "stop_price": Decimal("48000"),
        "take_profit_price": Decimal("55000"),
        "time_horizon": timedelta(days=1),
        "signal_ttl": timedelta(hours=1),
        "reasons": ("uptrend confirmed",),
        "risks": (),
        "supporting_signal_ids": (),
        "invalidating_conditions": (),
        "source_event_ids": (),
        "model_id": "model",
        "prompt_version": "v1",
        "as_of": AS_OF,
    }
    fields.update(overrides)
    return TradeProposal(**fields)  # type: ignore[arg-type]


def make_state(**overrides) -> PortfolioState:
    fields = {
        "equity": Decimal("10000"),
        "bucket_exposure": {},
        "asset_exposure": {},
        "open_positions": 0,
    }
    fields.update(overrides)
    return PortfolioState(**fields)


def make_risk_context(**overrides) -> RiskContext:
    fields = {
        "control_status": Status.RUNNING,
        "portfolio_state": make_state(),
        "portfolio_policy": PORTFOLIO_POLICY,
        "quality": QualityReport(status=QualityStatus.PASS, issues=()),
        "snapshot": MarketSnapshot(
            instrument=INSTRUMENT,
            bid=Decimal("49999"),
            ask=Decimal("50001"),
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


SERVICE = ShadowDecisionService(SimplePortfolioAllocator(), DeterministicRiskEngine())


def test_a_clean_long_proposal_is_approved_by_allocation_and_risk() -> None:
    outcome = SERVICE.evaluate(
        make_proposal(),
        Bucket.CORE,
        make_state(),
        PORTFOLIO_POLICY,
        make_risk_context(),
        RISK_POLICY,
    )
    assert outcome.allocation_approved is True
    assert outcome.risk_assessment is not None
    assert outcome.risk_assessment.decision == RiskDecision.APPROVED
    assert outcome.risk_assessment.final_notional > 0


def test_a_short_proposal_is_refused_before_allocation_or_risk() -> None:
    proposal = make_proposal(
        direction=TradeDirection.SHORT,
        stop_price=Decimal("52000"),
        take_profit_price=Decimal("45000"),
    )
    outcome = SERVICE.evaluate(
        proposal, Bucket.CORE, make_state(), PORTFOLIO_POLICY, make_risk_context(), RISK_POLICY
    )
    assert outcome.allocation_approved is False
    assert "SHORT" in outcome.allocation_reasons[0]
    assert outcome.risk_assessment is None


def test_a_full_speculative_bucket_is_rejected_at_allocation_before_risk_ever_runs() -> None:
    state = make_state(bucket_exposure={Bucket.SPECULATIVE: Decimal("1000")})
    context = make_risk_context(portfolio_state=state)
    outcome = SERVICE.evaluate(
        make_proposal(), Bucket.SPECULATIVE, state, PORTFOLIO_POLICY, context, RISK_POLICY
    )
    assert outcome.allocation_approved is False
    assert outcome.allocation_reasons
    assert outcome.risk_assessment is None


def test_risk_can_still_reject_an_allocation_approved_proposal() -> None:
    context = make_risk_context(daily_loss=Decimal("0.5"))
    outcome = SERVICE.evaluate(
        make_proposal(), Bucket.CORE, make_state(), PORTFOLIO_POLICY, context, RISK_POLICY
    )
    assert outcome.allocation_approved is True
    assert outcome.risk_assessment is not None
    assert outcome.risk_assessment.decision == RiskDecision.REJECTED
