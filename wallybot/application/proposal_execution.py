"""Revalidate an operator-approved AI proposal and, only if every deterministic control still
passes, submit one PAPER order on the operator's AI account (ADR-017).

The AI worker never reaches this module: it is called by the MFA-protected approval route after
the single-use approval is committed. Nothing the model produced is trusted as-is -- the
instrument, its precision, candles, quality, spread, equity, breakers and reconciliation are all
re-read at execution time, and the proposal runs through the same `ShadowDecisionService`
(allocator + `DeterministicRiskEngine`) the simulation uses. An expired proposal, a rejected
allocation or a rejected risk assessment produces no order. SELL can only reduce a held spot
position; the allocator/risk engine cap it by actual exposure.

`simulate_proposal` shares the same revalidation but has no gateway: it cannot submit anything.

Execution for all operators is serialized by one process-local lock: this API is the only writer
of `paper-ai:` accounts, and serializing keeps two approvals from both passing a capacity check
against the same balances before either fill is posted.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.decision_loop import BUCKET, PORTFOLIO_POLICY, RISK_POLICY
from wallybot.application.equity_tracker import EquityAssessment, assess_equity
from wallybot.application.execution_service import ExecutionService
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.application.shadow_decision_service import (
    ShadowDecisionOutcome,
    ShadowDecisionService,
)
from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import TIMEFRAME_DURATIONS, MarketDataProvider
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.domain.portfolio import PortfolioPolicy
from wallybot.domain.risk import ExchangeStatus, RiskContext, RiskDecision
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.models import ControlRow, TradeProposalRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.shadow_decision_repository import ShadowDecisionRepository
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator
from wallybot.risk.deterministic_risk_engine import DeterministicRiskEngine

ENVIRONMENT = "PAPER"
RISK_EXPIRY = timedelta(minutes=10)
QUALITY_POLICY = QualityPolicy(
    version=1,
    timeframe="1h",
    max_stale_age=timedelta(hours=3),
    max_clock_drift=timedelta(minutes=5),
    max_abnormal_return=Decimal("0.5"),
)
HISTORY_CANDLES = 20

_EXECUTION_LOCK = asyncio.Lock()


class ProposalExecutionStatus(StrEnum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ProposalExecutionResult:
    status: str
    client_order_id: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PaperAiExecution:
    """The AI account's own simulated venue. Kept apart from the deterministic PAPER gateway
    because `FakeExchange` holds one balance book, resynced from that account's ledger."""

    gateway: FakeExchange
    execution: ExecutionService
    reconciliation: ReconciliationService


def proposal_expires_at(row: TradeProposalRow) -> datetime:
    return row.as_of + timedelta(seconds=float(row.signal_ttl_seconds))


def is_proposal_expired(row: TradeProposalRow, now: datetime) -> bool:
    return proposal_expires_at(row) <= now


async def simulate_proposal(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    row: TradeProposalRow,
    account_id: str,
    now: datetime,
) -> ShadowDecisionOutcome:
    """Evidence only: the same revalidation an approval runs, without any gateway."""
    outcome = await _revalidate(sessions, provider, row, account_id, now, True)
    async with sessions.begin() as db:
        await ShadowDecisionRepository(db).save(outcome)
    return outcome


async def execute_approved_proposal(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    paper: PaperAiExecution,
    id_generator: IdGenerator,
    row: TradeProposalRow,
    account_id: str,
    now: datetime,
) -> ProposalExecutionResult:
    """Called only after the operator's approval is committed; never retried by itself."""
    if is_proposal_expired(row, now):
        return ProposalExecutionResult(
            ProposalExecutionStatus.EXPIRED, None, ("proposal signal TTL elapsed before approval",)
        )
    async with _EXECUTION_LOCK:
        async with sessions() as db:
            balances = await PortfolioRepository(db).list_balances(account_id)
        paper.gateway.balances = {balance.currency: balance.amount for balance in balances}
        swept = await paper.reconciliation.sweep(ENVIRONMENT, account_id)
        reconciliation_healthy = not any(item.error for item in swept) and not any(
            item.resolved_status is OrderStatus.UNKNOWN for item in swept
        )

        outcome = await _revalidate(
            sessions, provider, row, account_id, now, reconciliation_healthy
        )
        async with sessions.begin() as db:
            await ShadowDecisionRepository(db).save(outcome)
        if not outcome.allocation_approved:
            return ProposalExecutionResult(
                ProposalExecutionStatus.BLOCKED, None, outcome.allocation_reasons
            )
        assessment = outcome.risk_assessment
        if assessment is None or assessment.decision is RiskDecision.REJECTED:
            reasons = assessment.reasons if assessment is not None else ()
            return ProposalExecutionResult(ProposalExecutionStatus.BLOCKED, None, reasons)

        decision_id = id_generator.new_id()
        client_order_id = id_generator.new_id()
        intent = OrderIntent(
            account_id=account_id,
            environment=ENVIRONMENT,
            instrument=outcome.proposal.instrument,
            side=Side.BUY if outcome.proposal.direction is TradeDirection.LONG else Side.SELL,
            kind=OrderKind.MARKET,
            quantity=assessment.final_quantity,
            limit_price=None,
            decision_id=decision_id,
            client_order_id=client_order_id,
            idempotency_key=f"proposal:{row.proposal_id}",
            risk_assessment_id=decision_id,
            config_versions={
                "quality": QUALITY_POLICY.version,
                "portfolio": PORTFOLIO_POLICY.version,
                "risk": RISK_POLICY.version,
            },
            created_at=now,
            expires_at=assessment.expires_at,
            status=OrderStatus.VALIDATED,
        )
        status = await paper.execution.submit(intent)
        return ProposalExecutionResult(status.value, client_order_id, assessment.reasons)


async def _revalidate(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    row: TradeProposalRow,
    account_id: str,
    now: datetime,
    reconciliation_healthy: bool,
    equity: EquityAssessment | None = None,
    portfolio_policy: PortfolioPolicy = PORTFOLIO_POLICY,
) -> ShadowDecisionOutcome:
    instrument = next(
        (
            item
            for item in await provider.discover_instruments()
            if item.venue == row.venue and item.base == row.base and item.quote == row.quote
        ),
        None,
    )
    if instrument is None:
        raise LookupError("Proposal instrument is no longer available")
    candles = await provider.fetch_candles(
        instrument,
        QUALITY_POLICY.timeframe,
        now - TIMEFRAME_DURATIONS[QUALITY_POLICY.timeframe] * HISTORY_CANDLES,
        HISTORY_CANDLES,
    )
    quality = evaluate_series_quality(candles, QUALITY_POLICY, now)
    snapshot = await provider.fetch_snapshot(instrument)
    assessment = equity or await assess_equity(
        sessions, provider, account_id, ENVIRONMENT, row.quote, BUCKET, now, persist=False
    )
    async with sessions() as db:
        active_breakers = await BreakerRepository(db).list_active()
        control = await db.get(ControlRow, 1)
    proposal = TradeProposal(
        proposal_id=row.proposal_id,
        instrument=instrument,
        direction=TradeDirection(row.direction),
        strategy_id=row.strategy_id,
        confidence=row.confidence,
        suggested_allocation_pct=row.suggested_allocation_pct,
        entry_price=row.entry_price,
        stop_price=row.stop_price,
        take_profit_price=row.take_profit_price,
        time_horizon=timedelta(seconds=float(row.time_horizon_seconds)),
        signal_ttl=timedelta(seconds=float(row.signal_ttl_seconds)),
        reasons=tuple(str(value) for value in row.reasons),
        risks=tuple(str(value) for value in row.risks),
        supporting_signal_ids=tuple(str(value) for value in row.supporting_signal_ids),
        invalidating_conditions=tuple(str(value) for value in row.invalidating_conditions),
        source_event_ids=tuple(str(value) for value in row.source_event_ids),
        model_id=row.model_id,
        prompt_version=row.prompt_version,
        as_of=row.as_of,
    )
    return ShadowDecisionService(SimplePortfolioAllocator(), DeterministicRiskEngine()).evaluate(
        proposal,
        BUCKET,
        assessment.portfolio_state,
        portfolio_policy,
        RiskContext(
            control_status=Status(control.status) if control is not None else Status.PAUSED,
            portfolio_state=assessment.portfolio_state,
            portfolio_policy=portfolio_policy,
            quality=quality,
            snapshot=snapshot,
            exchange_status=ExchangeStatus.HEALTHY,
            reconciliation_healthy=reconciliation_healthy,
            active_breakers=frozenset(item.breaker_type.value for item in active_breakers),
            daily_loss=assessment.daily_loss,
            weekly_loss=assessment.weekly_loss,
            drawdown=assessment.drawdown,
            as_of=now,
            expiry=RISK_EXPIRY,
        ),
        RISK_POLICY,
    )
