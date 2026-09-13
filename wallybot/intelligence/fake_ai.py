"""Seeded, network-free AIProvider for deterministic tests -- the same "seeded Fake" pattern as
`FakeWalletIntelligenceProvider`/`FakeSecurityAnalysisProvider` applied to `wallybot.domain.
trade_proposal.AIProvider`.

No real model call, no API key, no plausible-random generator: no real AIProvider adapter is
integrated yet to give a generator something to imitate. This fake returns exactly one scripted
`TradeProposal` per instrument key, or `None` for anything not seeded -- never a fabricated
default, per `TradeProposal`'s own "no execution capability without evidence" rule.
"""

from wallybot.domain.market import Instrument
from wallybot.domain.trade_proposal import AIAnalysisContext, TradeProposal


class FakeAIProvider:
    """Implements wallybot.domain.trade_proposal.AIProvider (structural, not inherited)."""

    def __init__(self, proposals: dict[Instrument, TradeProposal] | None = None) -> None:
        self._proposals = proposals or {}

    async def analyze(self, context: AIAnalysisContext) -> TradeProposal | None:
        return self._proposals.get(context.instrument)
