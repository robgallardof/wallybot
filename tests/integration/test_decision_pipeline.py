import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.decision_pipeline import (
    DecisionPipeline,
    DecisionPipelineConfig,
    RiskEnvironment,
)
from wallybot.application.execution_service import ExecutionService
from wallybot.data.quality import QualityPolicy
from wallybot.domain.control import Status
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType
from wallybot.domain.order import OrderStatus
from wallybot.domain.portfolio import Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.risk import ExchangeStatus, RiskDecision, RiskPolicy
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.models import FillRow, LedgerPostingRow, OrderIntentRow
from wallybot.market.universe import UniverseFilterConfig
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine
from wallybot.signals.weighted_aggregator import WeightedSignalAggregator
from wallybot.strategies.trend_following import TrendFollowingStrategy

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 2, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="test",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


class SequentialIdGenerator:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"id-{self.counter}"


def _uptrend_candles(window: int, closes: list[Decimal]) -> list[Candle]:
    candles = []
    for i, close in enumerate(closes):
        open_time = NOW - timedelta(hours=window - i)
        close_time = open_time + timedelta(hours=1)
        candles.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=close_time,
                open=close,
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume=Decimal("10"),
                source="test",
                received_at=close_time,
            )
        )
    return candles


class ControlledProvider:
    """A MarketDataProvider that always returns the same hand-built, guaranteed-uptrend series --
    unlike FakeExchange's seeded random walk, this makes the resulting BUY signal deterministic
    and independent of any particular seed's luck."""

    def __init__(self, candles: list[Candle], snapshot: MarketSnapshot) -> None:
        self.candles = candles
        self.snapshot = snapshot

    async def discover_instruments(self) -> list[Instrument]:
        return [INSTRUMENT]

    async def fetch_candles(self, instrument, timeframe, since, limit) -> list[Candle]:
        return [c for c in self.candles if c.open_time >= since][:limit]

    async def fetch_snapshot(self, instrument) -> MarketSnapshot:
        return self.snapshot


def make_pipeline(
    sessions, execution: ExecutionService, closes: list[Decimal] | None = None
) -> DecisionPipeline:
    closes = closes if closes is not None else [Decimal(50000 + i * 1000) for i in range(20)]
    candles = _uptrend_candles(20, closes)
    last = closes[-1]
    snapshot = MarketSnapshot(
        instrument=INSTRUMENT,
        bid=last - Decimal("10"),
        ask=last + Decimal("10"),
        timestamp=NOW,
        source="test",
    )
    provider = ControlledProvider(candles, snapshot)

    config = DecisionPipelineConfig(
        timeframe="1h",
        history_candles=20,
        feature_window=20,
        max_finalists=5,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        portfolio_policy=PortfolioPolicy(
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
        ),
        risk_policy=RiskPolicy(
            version=1,
            max_daily_loss=Decimal("0.02"),
            max_weekly_loss=Decimal("0.05"),
            max_drawdown=Decimal("0.10"),
            max_spread_ratio=Decimal("0.01"),
        ),
        risk_off_threshold=Decimal("0.5"),
        risk_expiry=timedelta(minutes=5),
        account_id="acct-1",
        environment="PAPER",
        bucket=Bucket.CORE,
    )

    return DecisionPipeline(
        provider=provider,
        clock=FixedClock(NOW),
        id_generator=SequentialIdGenerator(),
        execution=execution,
        strategy=TrendFollowingStrategy(),
        aggregator=WeightedSignalAggregator(
            weights={"trend_following": Decimal("1")},
            min_quorum=1,
            min_agreement_ratio=Decimal("0.1"),
        ),
        allocator=SimplePortfolioAllocator(),
        risk_engine=DeterministicRiskEngine(),
        config=config,
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_execution_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE ledger_postings, ledger_transactions, ledger_accounts, fills, "
            "order_transitions, order_intents CASCADE"
        )
    yield


def make_state(**overrides: Any) -> PortfolioState:
    fields: dict[str, Any] = {
        "equity": Decimal("10000"),
        "bucket_exposure": {},
        "asset_exposure": {},
        "open_positions": 0,
    }
    fields.update(overrides)
    return PortfolioState(**fields)


HEALTHY_ENVIRONMENT = RiskEnvironment(
    control_status=Status.RUNNING,
    exchange_status=ExchangeStatus.HEALTHY,
    reconciliation_healthy=True,
    active_breakers=frozenset(),
    daily_loss=Decimal("0"),
    weekly_loss=Decimal("0"),
    drawdown=Decimal("0"),
)


async def test_an_uptrend_produces_a_real_filled_order_end_to_end(sessions) -> None:
    gateway = FakeExchange(clock=FixedClock(NOW), seed=1, balances={"USD": Decimal("1000000")})
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    pipeline = make_pipeline(sessions, execution)

    outcomes = await pipeline.run(make_state(), HEALTHY_ENVIRONMENT)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.instrument == INSTRUMENT
    assert outcome.order_status is OrderStatus.FILLED
    assert outcome.risk_assessment is not None
    assert outcome.risk_assessment.decision in (
        RiskDecision.APPROVED,
        RiskDecision.APPROVED_WITH_REDUCED_SIZE,
    )

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == OrderStatus.FILLED
        assert rows[0].quantity == outcome.risk_assessment.final_quantity

        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1

        postings = (await session.execute(select(LedgerPostingRow))).scalars().all()
        assert len(postings) == 4


async def test_a_bucket_already_at_its_ceiling_produces_no_order(sessions) -> None:
    gateway = FakeExchange(clock=FixedClock(NOW), seed=1, balances={"USD": Decimal("1000000")})
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    pipeline = make_pipeline(sessions, execution)

    # CORE's target is 70% of equity; exposure already at 100% of equity leaves no room at all.
    state = make_state(bucket_exposure={Bucket.CORE: Decimal("10000")})
    outcomes = await pipeline.run(state, HEALTHY_ENVIRONMENT)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.order_status is None
    assert outcome.risk_assessment is None
    assert outcome.reasons

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert rows == []


async def test_a_downtrend_with_an_open_position_produces_a_real_sell_fill(sessions) -> None:
    gateway = FakeExchange(
        clock=FixedClock(NOW),
        seed=1,
        balances={"USD": Decimal("1000000"), "BTC": Decimal("10")},
    )
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    downtrend_closes = [Decimal(69000 - i * 1000) for i in range(20)]
    pipeline = make_pipeline(sessions, execution, closes=downtrend_closes)

    # A held BTC position, notionally valued the same way `PortfolioState.asset_exposure` is
    # elsewhere in this codebase, is required for the allocator to size a reduction against.
    state = make_state(asset_exposure={INSTRUMENT.id: Decimal("3000")})
    outcomes = await pipeline.run(state, HEALTHY_ENVIRONMENT)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.instrument == INSTRUMENT
    assert outcome.order_status is OrderStatus.FILLED
    assert outcome.risk_assessment is not None
    assert outcome.risk_assessment.decision in (
        RiskDecision.APPROVED,
        RiskDecision.APPROVED_WITH_REDUCED_SIZE,
    )
    # Never more than what was actually held (3000), regardless of confidence.
    assert outcome.risk_assessment.final_notional <= Decimal("3000")

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert len(rows) == 1
        assert rows[0].side == "SELL"
        assert rows[0].status == OrderStatus.FILLED

        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1
        assert fills[0].side == "SELL"


async def test_a_risk_rejection_produces_no_order_but_is_still_reported(sessions) -> None:
    gateway = FakeExchange(clock=FixedClock(NOW), seed=1, balances={"USD": Decimal("1000000")})
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock(NOW))
    pipeline = make_pipeline(sessions, execution)

    # An active breaker blocks risk approval outright, after the allocator already said yes.
    environment = RiskEnvironment(
        control_status=Status.RUNNING,
        exchange_status=ExchangeStatus.HEALTHY,
        reconciliation_healthy=True,
        active_breakers=frozenset({"daily_loss"}),
        daily_loss=Decimal("0"),
        weekly_loss=Decimal("0"),
        drawdown=Decimal("0"),
    )
    outcomes = await pipeline.run(make_state(), environment)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.order_status is None
    assert outcome.risk_assessment is not None
    assert outcome.risk_assessment.decision is RiskDecision.REJECTED
    assert "breaker" in outcome.risk_assessment.reasons[0]

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert rows == []
