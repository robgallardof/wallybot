from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from wallybot.domain.control import Status
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.order import Side
from wallybot.domain.portfolio import AllocationProposal, Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityReport, QualityStatus
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

def _decimal(lo: str, hi: str, places: int) -> st.SearchStrategy[Decimal]:
    return st.decimals(
        min_value=lo, max_value=hi, places=places, allow_nan=False, allow_infinity=False
    )


@given(
    daily_loss=_decimal("0", "0.05", 4),
    weekly_loss=_decimal("0", "0.10", 4),
    drawdown=_decimal("0", "0.20", 4),
    core_exposure=_decimal("0", "9000", 2),
    proposed_notional=_decimal("0.01", "9000", 2),
    spread_fraction=_decimal("0", "0.05", 4),
)
def test_risk_assessment_invariants_hold_across_the_input_space(
    daily_loss, weekly_loss, drawdown, core_exposure, proposed_notional, spread_fraction
):
    """No matter how these dials are set, an assessment must always satisfy RISK.md's shape:
    REJECTED <=> zero notional; anything else <=> a positive notional never exceeding what was
    proposed; expiry strictly after as_of; evidence (reasons) always present. RiskAssessment's own
    __post_init__ already enforces the last two mechanically -- this test's job is the first two,
    which depend on the engine's logic, across inputs no hand-written example would have picked.
    """
    bid = Decimal("100")
    ask = bid * (1 + spread_fraction)
    snapshot = MarketSnapshot(
        instrument=INSTRUMENT, bid=bid, ask=ask, timestamp=AS_OF, source="fake"
    )
    proposal = AllocationProposal(
        instrument=INSTRUMENT,
        bucket=Bucket.CORE,
        side=Side.BUY,
        version=1,
        as_of=AS_OF,
        proposed_notional=proposed_notional,
        approved=True,
        reasons=(),
    )
    context = RiskContext(
        control_status=Status.RUNNING,
        portfolio_state=PortfolioState(
            equity=Decimal("10000"),
            bucket_exposure={Bucket.CORE: core_exposure},
            asset_exposure={},
            open_positions=0,
        ),
        portfolio_policy=PORTFOLIO_POLICY,
        quality=QualityReport(status=QualityStatus.PASS, issues=()),
        snapshot=snapshot,
        exchange_status=ExchangeStatus.HEALTHY,
        reconciliation_healthy=True,
        active_breakers=frozenset(),
        daily_loss=daily_loss,
        weekly_loss=weekly_loss,
        drawdown=drawdown,
        as_of=AS_OF,
        expiry=timedelta(minutes=5),
    )

    assessment = ENGINE.evaluate(proposal, context, POLICY)

    if assessment.decision == RiskDecision.REJECTED:
        assert assessment.final_notional == Decimal("0")
    else:
        assert Decimal("0") < assessment.final_notional <= proposed_notional
    assert assessment.expires_at > assessment.as_of
    assert assessment.reasons
