"""TradeProposalRepository: insert-only audit trail for `wallybot.domain.trade_proposal.
TradeProposal`.

`save` always inserts a new row -- there is no update path, matching every other Phase 10/11
snapshot repository's "a fresh evaluation is always a new row" guarantee. Per ARCHITECTURE.md's
"Every TradeProposal ... must be as auditable as an approved one," this is the durable evidence
record independent of whatever later happens to the proposal (a later slice's SHADOW-mode
wiring, not this one).

Deliberately write-only for now: reconstructing a full `TradeProposal` would require rebuilding
its `Instrument` from the stored venue/base/quote identity alone, and this table does not persist
price/quantity increments or minimum size -- the same reason `OrderIntentRow` and
`PriceConsensusResultRow` never reconstruct a full `Instrument` either (see `wallybot.
infrastructure.unit_of_work`). Fabricating those fields to satisfy a round trip would violate
RISK.md's "do not invent" rule. A future slice that actually needs to read proposals back defines
its own read shape against the columns this table really has.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.trade_proposal import TradeProposal
from wallybot.infrastructure.models import TradeProposalRow


class TradeProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, proposal: TradeProposal, owner_id: str | None = None) -> None:
        self.session.add(
            TradeProposalRow(
                proposal_id=proposal.proposal_id,
                venue=proposal.instrument.venue,
                base=proposal.instrument.base,
                quote=proposal.instrument.quote,
                direction=proposal.direction,
                strategy_id=proposal.strategy_id,
                confidence=proposal.confidence,
                suggested_allocation_pct=proposal.suggested_allocation_pct,
                entry_price=proposal.entry_price,
                stop_price=proposal.stop_price,
                take_profit_price=proposal.take_profit_price,
                time_horizon_seconds=Decimal(str(proposal.time_horizon.total_seconds())),
                signal_ttl_seconds=Decimal(str(proposal.signal_ttl.total_seconds())),
                reasons=list(proposal.reasons),
                risks=list(proposal.risks),
                supporting_signal_ids=list(proposal.supporting_signal_ids),
                invalidating_conditions=list(proposal.invalidating_conditions),
                source_event_ids=list(proposal.source_event_ids),
                model_id=proposal.model_id,
                prompt_version=proposal.prompt_version,
                as_of=proposal.as_of,
                owner_id=owner_id,
            )
        )
