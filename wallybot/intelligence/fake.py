"""Seeded, network-free WalletIntelligenceProvider for deterministic tests -- the "seeded Fake"
pattern this codebase already uses for market data (`wallybot/exchanges/fake.py`) and execution
(`FakeExchange`'s gateway half), applied to wallet intelligence.

Unlike `FakeExchange`'s candle generator, there is no plausible-random-walk generator here: no
real wallet-activity provider has been integrated yet to give a generator something to imitate.
This fake returns exactly what it was constructed with -- callers seed activity/labels explicitly
per wallet -- rather than inventing data with no real schema to validate against.
"""

from datetime import datetime

from wallybot.domain.entity import Attribution
from wallybot.domain.wallet_activity import WalletActivityEvent


class FakeWalletIntelligenceProvider:
    """Implements wallybot.domain.wallet_activity.WalletIntelligenceProvider (structural, not
    inherited)."""

    def __init__(
        self,
        activity: dict[str, list[WalletActivityEvent]] | None = None,
        labels: dict[str, tuple[Attribution, ...]] | None = None,
    ) -> None:
        self._activity = activity or {}
        self._labels = labels or {}

    async def fetch_wallet_activity(
        self, chain: str, address: str, since: datetime
    ) -> list[WalletActivityEvent]:
        events = self._activity.get(f"{chain}:{address}", [])
        return [event for event in events if event.occurred_at >= since]

    async def fetch_wallet_labels(self, chain: str, address: str) -> tuple[Attribution, ...]:
        return self._labels.get(f"{chain}:{address}", ())
