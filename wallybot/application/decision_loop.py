"""One tick of the live PAPER decision loop: resync simulated balances from the ledger, sweep
reconciliation, assess real equity, then run `DecisionPipeline`.

Closes the gap `DecisionPipeline`'s own docstring flagged: every downstream piece (allocator, risk
engine, execution service, ledger) was already real and tested, but nothing ever called `run()` in
production. The `while True` loop wrapper (`_decision_loop`) lives in `apps/api/main.py`, same
split as `_market_ingestion_loop`/`ingest_market_data` and `_price_consensus_loop`/
`run_price_consensus_tick`: only `apps/api` has internet egress to reach Kraken (PENDING.md Fase
7's `internal: true` network isolation for worker/scheduler/research), and only that process
resolves "which account" from real control/user state -- this module stays account-agnostic and
takes `account_id` as an input.

Single bucket (CORE, the most conservative) per tick -- `DecisionPipelineConfig` is still
single-bucket per run, the same simplification `wallybot.application.equity_tracker` already
documents; there is no per-instrument bucket assignment in this schema yet.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.decision_pipeline import (
    DecisionOutcome,
    DecisionPipeline,
    DecisionPipelineConfig,
    RiskEnvironment,
)
from wallybot.application.equity_tracker import assess_equity
from wallybot.application.execution_service import ExecutionService
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.data.quality import QualityPolicy
from wallybot.domain.clock import Clock
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import MarketDataProvider
from wallybot.domain.portfolio import Bucket, PortfolioPolicy
from wallybot.domain.risk import ExchangeStatus, RiskPolicy
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.market.universe import UniverseFilterConfig
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine
from wallybot.signals.weighted_aggregator import WeightedSignalAggregator
from wallybot.strategies.trend_following import TrendFollowingStrategy

CASH_CURRENCY = "USD"
BUCKET = Bucket.CORE

# RISK.md's own Initial Policy table, verbatim -- not invented here.
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
# RISK.md leaves spread/liquidity/slippage limits as "must be configured ... before eligible" with
# no universal default ("do not invent universally safe market thresholds") -- 1% reuses the one
# value this codebase's own risk-engine/allocator test suite has already established throughout
# (tests/unit/test_deterministic_risk_engine.py and friends), not a fresh invention here.
RISK_POLICY = RiskPolicy(
    version=1,
    max_daily_loss=Decimal("0.02"),
    max_weekly_loss=Decimal("0.05"),
    max_drawdown=Decimal("0.10"),
    max_spread_ratio=Decimal("0.01"),
)


@dataclass(frozen=True)
class DecisionTickResult:
    outcomes: tuple[DecisionOutcome, ...]
    reconciliation_healthy: bool


async def run_decision_tick(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    paper_gateway: FakeExchange,
    execution: ExecutionService,
    reconciliation: ReconciliationService,
    clock: Clock,
    id_generator: IdGenerator,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    account_id: str,
    now: datetime,
) -> DecisionTickResult:
    async with sessions() as db:
        balances = await PortfolioRepository(db).list_balances(account_id)
    # Resynced from the ledger every tick (the source of truth) rather than trusted to stay
    # correct across an unbounded number of ticks in FakeExchange's own in-memory bookkeeping --
    # e.g. a funding transaction posted between ticks must be picked up.
    paper_gateway.balances = {balance.currency: balance.amount for balance in balances}

    reconciliation_outcomes = await reconciliation.sweep("PAPER")
    reconciliation_healthy = not any(outcome.error for outcome in reconciliation_outcomes)

    assessment = await assess_equity(
        sessions, provider, account_id, "PAPER", CASH_CURRENCY, BUCKET, now
    )

    pipeline = DecisionPipeline(
        provider=provider,
        clock=clock,
        id_generator=id_generator,
        execution=execution,
        strategy=TrendFollowingStrategy(),
        aggregator=WeightedSignalAggregator(
            weights={"trend_following": Decimal("1")},
            min_quorum=1,
            min_agreement_ratio=Decimal("0.1"),
        ),
        allocator=SimplePortfolioAllocator(),
        risk_engine=DeterministicRiskEngine(),
        config=DecisionPipelineConfig(
            timeframe="1h",
            history_candles=20,
            feature_window=20,
            max_finalists=5,
            universe_config=universe_config,
            quality_policy=quality_policy,
            portfolio_policy=PORTFOLIO_POLICY,
            risk_policy=RISK_POLICY,
            risk_off_threshold=Decimal("0.5"),
            risk_expiry=timedelta(minutes=10),
            account_id=account_id,
            environment="PAPER",
            bucket=BUCKET,
        ),
    )
    risk_environment = RiskEnvironment(
        control_status=Status.RUNNING,
        # No dedicated exchange-health monitor exists yet -- a failed data fetch already raises
        # out of this tick before risk evaluation is ever reached (the loop wrapper catches it),
        # so treating the exchange as healthy here never masks a real outage.
        exchange_status=ExchangeStatus.HEALTHY,
        reconciliation_healthy=reconciliation_healthy,
        # No persistent operational-breaker subsystem exists yet (stale data/exchange outage/
        # repeated errors, per RISK.md) -- only the daily/weekly loss and drawdown breakers below
        # are real. Not fabricated as "no breakers active"; explicitly narrower in scope than
        # RISK.md's full breaker taxonomy.
        active_breakers=frozenset(),
        daily_loss=assessment.daily_loss,
        weekly_loss=assessment.weekly_loss,
        drawdown=assessment.drawdown,
    )
    outcomes = await pipeline.run(assessment.portfolio_state, risk_environment)
    return DecisionTickResult(outcomes=outcomes, reconciliation_healthy=reconciliation_healthy)
