"""Conservative agreement gate for independent, analyst-only AI providers.

This adapter has no market, portfolio, credential, execution or transfer dependency. It asks
each configured analyst to evaluate the same immutable context and returns a proposal only when
the configured agreement rule permits it. A missing response, malformed provider output, or
materially different entry price fails closed to HOLD (``None``).
"""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from wallybot.domain.trade_proposal import AIAnalysisContext, AIProvider, TradeProposal


@dataclass(frozen=True)
class ConsensusAiProvider:
    """Combine independent analysts without giving either one operational authority."""

    providers: tuple[AIProvider, ...]
    require_consensus: bool = True
    max_entry_price_deviation_pct: Decimal = Decimal("0.03")

    def __post_init__(self) -> None:
        if not self.providers:
            raise ValueError("at least one analyst provider is required")
        if not (Decimal(0) <= self.max_entry_price_deviation_pct <= Decimal("0.10")):
            raise ValueError("max_entry_price_deviation_pct must be between 0 and 0.10")

    async def analyze(self, context: AIAnalysisContext) -> TradeProposal | None:
        results = await asyncio.gather(*(provider.analyze(context) for provider in self.providers))
        proposals = tuple(item for item in results if item is not None)
        if not proposals:
            return None
        if self.require_consensus and len(proposals) != len(self.providers):
            return None

        primary = proposals[0]
        if any(not self._proposals_agree(primary, proposal) for proposal in proposals[1:]):
            return None
        return self._combine(primary, proposals)

    def _proposals_agree(self, primary: TradeProposal, other: TradeProposal) -> bool:
        return primary.direction is other.direction and (
            abs(primary.entry_price - other.entry_price) / primary.entry_price
            <= self.max_entry_price_deviation_pct
        )

    @staticmethod
    def _combine(primary: TradeProposal, proposals: Iterable[TradeProposal]) -> TradeProposal:
        proposals = tuple(proposals)
        analyst_models = tuple(proposal.model_id for proposal in proposals)
        reasons = (
            f"Independent analyst consensus: {', '.join(analyst_models)}",
            *primary.reasons,
        )
        risks = tuple(dict.fromkeys(risk for proposal in proposals for risk in proposal.risks))
        supporting_signal_ids = tuple(
            dict.fromkeys(
                signal_id for proposal in proposals for signal_id in proposal.supporting_signal_ids
            )
        )
        return TradeProposal(
            proposal_id=primary.proposal_id,
            instrument=primary.instrument,
            direction=primary.direction,
            strategy_id="ai-consensus",
            confidence=min(proposal.confidence for proposal in proposals),
            suggested_allocation_pct=min(
                proposal.suggested_allocation_pct for proposal in proposals
            ),
            entry_price=primary.entry_price,
            stop_price=primary.stop_price,
            take_profit_price=primary.take_profit_price,
            time_horizon=primary.time_horizon,
            signal_ttl=primary.signal_ttl,
            reasons=reasons,
            risks=risks,
            supporting_signal_ids=supporting_signal_ids,
            invalidating_conditions=primary.invalidating_conditions,
            source_event_ids=primary.source_event_ids,
            model_id="consensus:" + "+".join(analyst_models),
            prompt_version="consensus/"
            + "+".join(proposal.prompt_version for proposal in proposals),
            as_of=primary.as_of,
        )
