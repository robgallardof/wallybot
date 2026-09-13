"""ShadowDecisionService: run a TradeProposal through the same PortfolioAllocator/RiskEngine gate
the deterministic DecisionPipeline uses, without ever holding a reference to ExecutionService or
an IdGenerator -- so it is structurally incapable of submitting an order, not merely "chosen" not
to. Per ARCHITECTURE.md's implementation sequence: "AI strategy engine ... SHADOW mode before any
LIVE eligibility."

This reuses `PortfolioAllocator.propose`/`RiskEngine.evaluate` exactly as `DecisionPipeline` does,
rather than re-implementing sizing or risk logic: a `TradeProposal` is translated into the same
`AggregatedSignal` shape `SignalAggregator` would have produced, so both paths flow through
identical, already-tested allocation and risk code. `contributing_signals` is empty (there is no
underlying `StrategySignal` for an AI-sourced proposal); the proposal's own `reasons` fill the
`reason` field instead.

SHORT proposals are refused before allocation, same reasoning `DecisionPipeline` already applies
to SELL: `SimplePortfolioAllocator` has no position data to size a reduction against.

Deliberately out of scope: persistence (a separate insert-only repository), any caller-side
decision about running this automatically, and anything resembling promotion from SHADOW to LIVE
eligibility (RISK.md's evidence gates, not built here).
"""

from dataclasses import dataclass
from datetime import datetime

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.portfolio import (
    Bucket,
    PortfolioAllocator,
    PortfolioPolicy,
    PortfolioState,
)
from wallybot.domain.risk import RiskAssessment, RiskContext, RiskEngine, RiskPolicy
from wallybot.domain.strategy import Action
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal

SHADOW_SIGNAL_VERSION = 1


@dataclass(frozen=True)
class ShadowDecisionOutcome:
    proposal: TradeProposal
    allocation_approved: bool
    allocation_reasons: tuple[str, ...]
    risk_assessment: RiskAssessment | None
    as_of: datetime


class ShadowDecisionService:
    def __init__(self, allocator: PortfolioAllocator, risk_engine: RiskEngine) -> None:
        self.allocator = allocator
        self.risk_engine = risk_engine

    def evaluate(
        self,
        proposal: TradeProposal,
        bucket: Bucket,
        portfolio_state: PortfolioState,
        portfolio_policy: PortfolioPolicy,
        risk_context: RiskContext,
        risk_policy: RiskPolicy,
    ) -> ShadowDecisionOutcome:
        if proposal.direction is TradeDirection.SHORT:
            return ShadowDecisionOutcome(
                proposal=proposal,
                allocation_approved=False,
                allocation_reasons=(
                    "SHORT is not yet supported: no position data exists to size a reduction",
                ),
                risk_assessment=None,
                as_of=proposal.as_of,
            )

        signal = AggregatedSignal(
            instrument=proposal.instrument,
            action=Action.BUY,
            confidence=proposal.confidence,
            version=SHADOW_SIGNAL_VERSION,
            as_of=proposal.as_of,
            contributing_signals=(),
            reason="; ".join(proposal.reasons),
        )
        allocation = self.allocator.propose(
            signal, bucket, portfolio_state, portfolio_policy, proposal.as_of
        )
        if not allocation.approved:
            return ShadowDecisionOutcome(
                proposal=proposal,
                allocation_approved=False,
                allocation_reasons=allocation.reasons,
                risk_assessment=None,
                as_of=proposal.as_of,
            )

        assessment = self.risk_engine.evaluate(allocation, risk_context, risk_policy)
        return ShadowDecisionOutcome(
            proposal=proposal,
            allocation_approved=True,
            allocation_reasons=(),
            risk_assessment=assessment,
            as_of=proposal.as_of,
        )
