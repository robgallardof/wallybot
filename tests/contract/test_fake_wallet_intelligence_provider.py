from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tests.contract.wallet_intelligence_provider_suite import (
    assert_fetch_wallet_activity_for_an_unknown_wallet_is_empty,
    assert_fetch_wallet_activity_respects_since,
    assert_fetch_wallet_labels_for_an_unknown_wallet_is_empty,
)
from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.intelligence.fake import FakeWalletIntelligenceProvider

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_event(occurred_at: datetime) -> WalletActivityEvent:
    return WalletActivityEvent(
        wallet_id="solana:abc123",
        chain="solana",
        transaction_hash=f"tx-{occurred_at.isoformat()}",
        token="SOL",
        action=OnChainActionType.SWAP,
        amount=Decimal("1"),
        value_usd=Decimal("150"),
        price=Decimal("150"),
        liquidity_usd=Decimal("500000"),
        occurred_at=occurred_at,
        attribution=Attribution(
            source="helius",
            source_entity_id=None,
            confidence=Decimal("0.9"),
            evidence="on-chain swap transaction",
            verification_status=VerificationStatus.VERIFIED,
            observed_at=occurred_at,
        ),
    )


def make_provider() -> FakeWalletIntelligenceProvider:
    early = make_event(NOW - timedelta(hours=2))
    late = make_event(NOW)
    return FakeWalletIntelligenceProvider(
        activity={"solana:abc123": [early, late]},
        labels={
            "solana:abc123": (
                Attribution(
                    source="nansen",
                    source_entity_id=None,
                    confidence=Decimal("0.8"),
                    evidence="labeled smart-money wallet",
                    verification_status=VerificationStatus.UNVERIFIED,
                    observed_at=NOW,
                ),
            )
        },
    )


async def test_fetch_wallet_activity_respects_since() -> None:
    await assert_fetch_wallet_activity_respects_since(
        make_provider(), "solana", "abc123", NOW - timedelta(hours=1)
    )


async def test_fetch_wallet_activity_for_an_unknown_wallet_is_empty() -> None:
    await assert_fetch_wallet_activity_for_an_unknown_wallet_is_empty(
        make_provider(), "solana", "never-seen", NOW - timedelta(days=1)
    )


async def test_fetch_wallet_labels_for_an_unknown_wallet_is_empty() -> None:
    await assert_fetch_wallet_labels_for_an_unknown_wallet_is_empty(
        make_provider(), "solana", "never-seen"
    )


async def test_fetch_wallet_activity_since_filter_excludes_earlier_events() -> None:
    provider = make_provider()
    events = await provider.fetch_wallet_activity("solana", "abc123", NOW - timedelta(minutes=30))
    assert len(events) == 1
    assert events[0].occurred_at == NOW


async def test_fetch_wallet_labels_returns_seeded_attributions() -> None:
    provider = make_provider()
    labels = await provider.fetch_wallet_labels("solana", "abc123")
    assert len(labels) == 1
    assert labels[0].source == "nansen"
