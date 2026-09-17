"""DecisionPipeline: the first closed loop from market data to a submitted order.

Composes every capability Phases 2-4 already built and tested separately, exactly in
ARCHITECTURE.md's own stated order: "Collectors normalize data; quality checks gate features;
universe filters reject unavailable, illiquid, wide-spread, insufficient-history or unsafe
markets. Versioned scoring ranks finalists. Regime classification and strategies produce signals.
... Allocation proposes size; risk has final veto." An approved risk assessment becomes an
`OrderIntent`, submitted through `ExecutionService` (Phase 4).

Adds no new decision logic of its own -- every accept/reject rule already lives in the composed
pieces (`evaluate_series_quality`, `evaluate_universe`, `classify_regime`, the injected
`Strategy`/`SignalAggregator`/`PortfolioAllocator`/`RiskEngine`). A HOLD signal, an unapproved
allocation proposal or a REJECTED risk assessment all end the pipeline for that instrument with no
`OrderIntent` ever created -- that is this pipeline's most common, fully correct outcome, not a
failure needing special handling.

BUY and SELL both flow through the same allocator/risk path -- `SimplePortfolioAllocator.propose`
sizes a SELL as a reduction of the instrument's own currently-held exposure (never a short), and
`DeterministicRiskEngine` caps it at exactly what `PortfolioState.asset_exposure` reports is held,
never at bucket/concentration headroom (that only constrains a BUY).

Explicitly out of scope: computing `PortfolioState`/loss/drawdown/breaker inputs (there is no
equity or PnL tracker yet -- a caller supplies `RiskEnvironment` and `PortfolioState` from
whatever it currently knows, same as `RiskContext` already required); persisting the decision
itself as its own durable record (DATA.md names a `decisions` collection; this pipeline generates
a fresh `decision_id`/`risk_assessment_id` per attempt but nothing persists a `RiskAssessment` on
its own -- only the `OrderIntent` it produces is durable, via `ExecutionService`); scheduling (a
caller decides when and how often `run()` executes); multi-strategy consensus beyond whatever
`SignalAggregator` is injected with.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from wallybot.application.execution_service import ExecutionService
from wallybot.application.scanner import scan_universe
from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.aggregation import SignalAggregator
from wallybot.domain.clock import Clock
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import TIMEFRAME_DURATIONS, Instrument, MarketDataProvider
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.domain.portfolio import (
    Bucket,
    PortfolioAllocator,
    PortfolioPolicy,
    PortfolioState,
)
from wallybot.domain.quality import QualityStatus
from wallybot.domain.regime import classify_regime
from wallybot.domain.risk import (
    ExchangeStatus,
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskEngine,
    RiskPolicy,
)
from wallybot.domain.strategy import Action, Strategy, StrategyContext
from wallybot.market.universe import UniverseFilterConfig


@dataclass(frozen=True)
class RiskEnvironment:
    """The `RiskContext` fields that do not vary per instrument within one `run()` call."""

    control_status: Status
    exchange_status: ExchangeStatus
    reconciliation_healthy: bool
    active_breakers: frozenset[str]
    daily_loss: Decimal
    weekly_loss: Decimal
    drawdown: Decimal


@dataclass(frozen=True)
class DecisionPipelineConfig:
    timeframe: str
    history_candles: int
    feature_window: int
    max_finalists: int
    universe_config: UniverseFilterConfig
    quality_policy: QualityPolicy
    portfolio_policy: PortfolioPolicy
    risk_policy: RiskPolicy
    risk_off_threshold: Decimal
    risk_expiry: timedelta
    account_id: str
    environment: Literal["PAPER", "LIVE"]
    bucket: Bucket


@dataclass(frozen=True)
class DecisionOutcome:
    instrument: Instrument
    order_status: OrderStatus | None
    risk_assessment: RiskAssessment | None
    reasons: tuple[str, ...]


class DecisionPipeline:
    def __init__(
        self,
        provider: MarketDataProvider,
        clock: Clock,
        id_generator: IdGenerator,
        execution: ExecutionService,
        strategy: Strategy,
        aggregator: SignalAggregator,
        allocator: PortfolioAllocator,
        risk_engine: RiskEngine,
        config: DecisionPipelineConfig,
    ) -> None:
        self.provider = provider
        self.clock = clock
        self.id_generator = id_generator
        self.execution = execution
        self.strategy = strategy
        self.aggregator = aggregator
        self.allocator = allocator
        self.risk_engine = risk_engine
        self.config = config

    async def run(
        self, portfolio_state: PortfolioState, risk_environment: RiskEnvironment
    ) -> tuple[DecisionOutcome, ...]:
        now = self.clock.now()
        step = TIMEFRAME_DURATIONS[self.config.timeframe]
        since = now - step * self.config.history_candles
        instruments = await self.provider.discover_instruments()

        candles_by_id = {}
        snapshots_by_id = {}
        quality_by_id = {}
        for instrument in instruments:
            candles = await self.provider.fetch_candles(
                instrument, self.config.timeframe, since, self.config.history_candles
            )
            candles_by_id[instrument.id] = candles
            snapshots_by_id[instrument.id] = await self.provider.fetch_snapshot(instrument)
            quality_by_id[instrument.id] = evaluate_series_quality(
                candles, self.config.quality_policy, now
            )

        # Quality is a separate, earlier gate than universe eligibility (staleness/clock-skew/
        # abnormal-return vs. history-length/volume/spread) -- an instrument with bad data never
        # reaches scoring at all, regardless of how liquid or well-covered it otherwise looks.
        candidate_instruments = [
            instrument
            for instrument in instruments
            if quality_by_id[instrument.id].status != QualityStatus.FAILURE
        ]

        scan = scan_universe(
            candidate_instruments,
            candles_by_id,
            snapshots_by_id,
            self.config.universe_config,
            now,
            self.config.feature_window,
            self.config.max_finalists,
        )

        outcomes = []
        for score in scan.finalists:
            outcomes.append(
                await self._decide_one(
                    score.inputs,
                    quality_by_id,
                    snapshots_by_id,
                    portfolio_state,
                    risk_environment,
                    now,
                )
            )
        return tuple(outcomes)

    async def _decide_one(
        self, vector, quality_by_id, snapshots_by_id, portfolio_state, risk_environment, now
    ) -> DecisionOutcome:
        instrument = vector.instrument
        regime = classify_regime(vector, self.config.risk_off_threshold)
        signal = self.strategy.evaluate(
            StrategyContext(instrument=instrument, features=vector, regime=regime, as_of=now)
        )
        aggregated = self.aggregator.aggregate([signal], now)

        if aggregated.action is Action.HOLD:
            return DecisionOutcome(
                instrument, None, None, (f"aggregated signal is HOLD: {aggregated.reason}",)
            )

        proposal = self.allocator.propose(
            aggregated, self.config.bucket, portfolio_state, self.config.portfolio_policy, now
        )
        if not proposal.approved:
            return DecisionOutcome(instrument, None, None, proposal.reasons)

        risk_context = RiskContext(
            control_status=risk_environment.control_status,
            portfolio_state=portfolio_state,
            portfolio_policy=self.config.portfolio_policy,
            quality=quality_by_id[instrument.id],
            snapshot=snapshots_by_id[instrument.id],
            exchange_status=risk_environment.exchange_status,
            reconciliation_healthy=risk_environment.reconciliation_healthy,
            active_breakers=risk_environment.active_breakers,
            daily_loss=risk_environment.daily_loss,
            weekly_loss=risk_environment.weekly_loss,
            drawdown=risk_environment.drawdown,
            as_of=now,
            expiry=self.config.risk_expiry,
        )
        assessment = self.risk_engine.evaluate(proposal, risk_context, self.config.risk_policy)
        if assessment.decision is RiskDecision.REJECTED:
            return DecisionOutcome(instrument, None, assessment, assessment.reasons)

        intent = self._build_order_intent(instrument, proposal.side, assessment, now)
        status = await self.execution.submit(intent)
        return DecisionOutcome(instrument, status, assessment, assessment.reasons)

    def _build_order_intent(
        self, instrument: Instrument, side: Side, assessment: RiskAssessment, now: datetime
    ) -> OrderIntent:
        decision_id = self.id_generator.new_id()
        client_order_id = self.id_generator.new_id()
        return OrderIntent(
            account_id=self.config.account_id,
            environment=self.config.environment,
            instrument=instrument,
            side=side,
            kind=OrderKind.MARKET,
            quantity=assessment.final_quantity,
            limit_price=None,
            decision_id=decision_id,
            client_order_id=client_order_id,
            idempotency_key=client_order_id,
            risk_assessment_id=decision_id,
            config_versions={
                "universe": self.config.universe_config.version,
                "quality": self.config.quality_policy.version,
                "portfolio": self.config.portfolio_policy.version,
                "risk": self.config.risk_policy.version,
            },
            created_at=now,
            expires_at=assessment.expires_at,
            status=OrderStatus.VALIDATED,
        )
