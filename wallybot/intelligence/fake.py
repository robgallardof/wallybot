"""Seeded, network-free WalletIntelligenceProvider for deterministic tests -- the "seeded Fake"
pattern this codebase already uses for market data (`wallybot/exchanges/fake.py`) and execution
(`FakeExchange`'s gateway half), applied to wallet intelligence.

Unlike `FakeExchange`'s candle generator, there is no plausible-random-walk generator here: no
real wallet-activity provider has been integrated yet to give a generator something to imitate.
This fake returns exactly what it was constructed with -- callers seed activity/labels explicitly
per wallet -- rather than inventing data with no real schema to validate against.
"""

from datetime import datetime

from wallybot.domain.clock import Clock
from wallybot.domain.entity import Attribution
from wallybot.domain.token_risk import SecurityAnalysisResult
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


class FakeSecurityAnalysisProvider:
    """Implements wallybot.domain.token_risk.SecurityAnalysisProvider (structural, not
    inherited). No real vendor (GoPlus, Honeypot.is, TokenSniffer, RugCheck, ...) is integrated
    yet, so -- same reasoning as `FakeWalletIntelligenceProvider` -- this returns exactly what it
    was seeded with rather than inventing a schema no real provider has been checked against.

    A token that was never seeded gets an all-`None` result, not an exception: a real security
    scanner always answers a valid query, it just may have nothing to report -- the same "unknown
    wallet returns an empty activity list, never a raised error" contract
    `FakeWalletIntelligenceProvider` already follows."""

    def __init__(
        self, clock: Clock, results: dict[str, SecurityAnalysisResult] | None = None
    ) -> None:
        self.clock = clock
        self._results = results or {}

    async def analyze_token(self, chain: str, token_id: str) -> SecurityAnalysisResult:
        key = f"{chain}:{token_id}"
        result = self._results.get(key)
        if result is not None:
            return result
        return SecurityAnalysisResult(
            token_id=token_id,
            chain=chain,
            mint_authority_active=None,
            freeze_authority_active=None,
            liquidity_locked=None,
            buy_tax_pct=None,
            sell_tax_pct=None,
            is_honeypot=None,
            malicious_labels=None,
            source="fake",
            fetched_at=self.clock.now(),
        )
