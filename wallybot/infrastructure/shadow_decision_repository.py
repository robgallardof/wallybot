"""ShadowDecisionRepository: insert-only audit trail for `wallybot.application.
shadow_decision_service.ShadowDecisionOutcome`.

`save` always inserts a new row -- no update path, same discipline as every other outcome/
snapshot repository in this codebase. Write-only: nothing yet needs to reconstruct a
`ShadowDecisionOutcome` domain object from a row (it carries the full `TradeProposal`, which
would hit the same "no full Instrument fidelity persisted" issue `TradeProposalRepository`
already documents) -- a future evaluation/reporting consumer defines its own read shape against
these columns instead.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.application.shadow_decision_service import ShadowDecisionOutcome
from wallybot.infrastructure.models import ShadowDecisionRow


class ShadowDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, outcome: ShadowDecisionOutcome) -> None:
        assessment = outcome.risk_assessment
        self.session.add(
            ShadowDecisionRow(
                proposal_id=outcome.proposal.proposal_id,
                venue=outcome.proposal.instrument.venue,
                base=outcome.proposal.instrument.base,
                quote=outcome.proposal.instrument.quote,
                allocation_approved=outcome.allocation_approved,
                allocation_reasons=list(outcome.allocation_reasons),
                risk_decision=assessment.decision.value if assessment is not None else None,
                risk_final_notional=(assessment.final_notional if assessment is not None else None),
                risk_final_quantity=(assessment.final_quantity if assessment is not None else None),
                risk_reasons=list(assessment.reasons) if assessment is not None else None,
                as_of=outcome.as_of,
            )
        )
