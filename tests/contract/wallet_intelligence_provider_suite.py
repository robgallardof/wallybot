"""Shared contract suite: any WalletIntelligenceProvider (FakeWalletIntelligenceProvider today; a
real vendor adapter later) must satisfy this. Mirrors market_data_provider_suite.py's pattern --
import these functions from a per-adapter test module rather than parametrizing here.
"""

from datetime import datetime

from wallybot.domain.wallet_activity import WalletIntelligenceProvider


async def assert_fetch_wallet_activity_respects_since(
    provider: WalletIntelligenceProvider,
    chain: str,
    address: str,
    since: datetime,
) -> None:
    events = await provider.fetch_wallet_activity(chain, address, since)
    for event in events:
        assert event.occurred_at >= since
        assert event.wallet_id == f"{chain}:{address}"


async def assert_fetch_wallet_activity_for_an_unknown_wallet_is_empty(
    provider: WalletIntelligenceProvider, chain: str, address: str, since: datetime
) -> None:
    events = await provider.fetch_wallet_activity(chain, address, since)
    assert events == []


async def assert_fetch_wallet_labels_for_an_unknown_wallet_is_empty(
    provider: WalletIntelligenceProvider, chain: str, address: str
) -> None:
    labels = await provider.fetch_wallet_labels(chain, address)
    assert labels == ()
