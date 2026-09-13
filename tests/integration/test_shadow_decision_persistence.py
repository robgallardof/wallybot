import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.shadow_decision_service import ShadowDecisionService
from wallybot.domain.control import Status
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.portfolio import Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityReport, QualityStatus
from wallybot.domain.risk import ExchangeStatus, RiskContext, RiskPolicy
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal
from wallybot.infrastructure.models import OrderIntentRow, ShadowDecisionRow
from wallybot.infrastructure.shadow_decision_repository import ShadowDecisionRepository
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


AS_OF = datetime(2026, 1, 10, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="kraken",
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


def make_proposal() -> TradeProposal:
    return TradeProposal(
        proposal_id="prop-shadow-1",
        instrument=INSTRUMENT,
        direction=TradeDirection.LONG,
        strategy_id="ai-v1",
        confidence=Decimal("0.8"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=Decimal("50000"),
        stop_price=Decimal("48000"),
        take_profit_price=Decimal("55000"),
        time_horizon=timedelta(days=1),
        signal_ttl=timedelta(hours=1),
        reasons=("uptrend confirmed",),
        risks=(),
        supporting_signal_ids=(),
        invalidating_conditions=(),
        source_event_ids=(),
        model_id="model",
        prompt_version="v1",
        as_of=AS_OF,
    )


def make_risk_context() -> RiskContext:
    return RiskContext(
        control_status=Status.RUNNING,
        portfolio_state=PortfolioState(
            equity=Decimal("10000"), bucket_exposure={}, asset_exposure={}, open_positions=0
        ),
        portfolio_policy=PORTFOLIO_POLICY,
        quality=QualityReport(status=QualityStatus.PASS, issues=()),
        snapshot=MarketSnapshot(
            instrument=INSTRUMENT,
            bid=Decimal("49999"),
            ask=Decimal("50001"),
            timestamp=AS_OF,
            source="fake",
        ),
        exchange_status=ExchangeStatus.HEALTHY,
        reconciliation_healthy=True,
        active_breakers=frozenset(),
        daily_loss=Decimal("0"),
        weekly_loss=Decimal("0"),
        drawdown=Decimal("0"),
        as_of=AS_OF,
        expiry=timedelta(minutes=5),
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE shadow_decisions, order_intents CASCADE")
    yield


async def test_a_shadow_evaluation_persists_the_full_outcome_and_never_touches_order_intents(
    sessions,
) -> None:
    service = ShadowDecisionService(SimplePortfolioAllocator(), DeterministicRiskEngine())
    outcome = service.evaluate(
        make_proposal(),
        Bucket.CORE,
        PortfolioState(
            equity=Decimal("10000"), bucket_exposure={}, asset_exposure={}, open_positions=0
        ),
        PORTFOLIO_POLICY,
        make_risk_context(),
        RISK_POLICY,
    )
    assert outcome.allocation_approved is True
    assert outcome.risk_assessment is not None

    async with sessions.begin() as session:
        await ShadowDecisionRepository(session).save(outcome)

    async with sessions() as session:
        rows = (await session.execute(select(ShadowDecisionRow))).scalars().all()
        order_intents = (await session.execute(select(OrderIntentRow))).scalars().all()

    assert len(rows) == 1
    row = rows[0]
    assert row.proposal_id == "prop-shadow-1"
    assert row.allocation_approved is True
    assert row.risk_decision == outcome.risk_assessment.decision.value
    assert row.risk_final_notional == outcome.risk_assessment.final_notional
    assert row.risk_final_quantity == outcome.risk_assessment.final_quantity
    # The whole point of SHADOW mode: this evaluation never creates an order, at any layer.
    assert order_intents == []
