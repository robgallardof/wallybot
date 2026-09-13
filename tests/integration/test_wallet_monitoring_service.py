import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.wallet_monitoring_service import WalletMonitoringService
from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet import Wallet
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.infrastructure.wallet_activity_repository import WalletActivityRepository
from wallybot.infrastructure.wallet_repository import WalletRepository
from wallybot.intelligence.fake import FakeWalletIntelligenceProvider

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "helius",
        "source_entity_id": None,
        "confidence": Decimal("0.9"),
        "evidence": "on-chain swap transaction",
        "verification_status": VerificationStatus.VERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_event(transaction_hash: str, occurred_at: datetime) -> WalletActivityEvent:
    return WalletActivityEvent(
        wallet_id="solana:abc123",
        chain="solana",
        transaction_hash=transaction_hash,
        token="SOL",
        action=OnChainActionType.SWAP,
        amount=Decimal("1"),
        value_usd=Decimal("150"),
        price=Decimal("150"),
        liquidity_usd=Decimal("500000"),
        occurred_at=occurred_at,
        attribution=make_attribution(observed_at=occurred_at),
    )


def make_wallet(**overrides: Any) -> Wallet:
    fields: dict[str, Any] = {
        "address": "abc123",
        "chain": "solana",
        "entity_id": None,
        "alias": None,
        "labels": (),
        "tags": (),
        "confidence": Decimal("0.7"),
        "trust_score": Decimal("0.6"),
        "risk_score": Decimal("0.1"),
        "enabled": True,
        "influence_weight": Decimal("0.3"),
        "max_signal_weight": Decimal("0.2"),
        "max_allocation": None,
        "min_transaction_value": Decimal("0"),
        "attributions": (make_attribution(),),
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return Wallet(**fields)


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_wallet_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE wallet_activity_events, wallet_cluster_members, wallet_clusters, "
            "wallet_attributions, wallets, entity_attributions, entities CASCADE"
        )
    yield


async def test_sync_wallet_persists_new_events_and_skips_already_known_ones(sessions) -> None:
    # sync_wallet ingests activity for a wallet the registry already knows about -- the FK from
    # wallet_activity_events to wallets exists precisely to make an unregistered wallet's
    # "activity" a loud error rather than a silently accepted orphan row.
    async with sessions.begin() as session:
        await WalletRepository(session).save(make_wallet())

    early = make_event("tx-1", NOW - timedelta(hours=2))
    late = make_event("tx-2", NOW)
    provider = FakeWalletIntelligenceProvider(activity={"solana:abc123": [early, late]})
    service = WalletMonitoringService(provider=provider, sessions=sessions)

    new_events = await service.sync_wallet("solana", "abc123", NOW - timedelta(days=1))
    assert {e.transaction_hash for e in new_events} == {"tx-1", "tx-2"}

    async with sessions() as session:
        stored = await WalletActivityRepository(session).list_for_wallet("solana", "abc123")
    assert len(stored) == 2

    # Re-syncing an overlapping window must not duplicate what's already known.
    new_events_again = await service.sync_wallet("solana", "abc123", NOW - timedelta(days=1))
    assert new_events_again == ()

    async with sessions() as session:
        stored_again = await WalletActivityRepository(session).list_for_wallet("solana", "abc123")
    assert len(stored_again) == 2


async def test_sync_all_enabled_wallets_covers_every_enabled_wallet_and_skips_disabled_ones(
    sessions,
) -> None:
    enabled = make_wallet(address="abc123")
    disabled = make_wallet(address="def456", enabled=False)
    async with sessions.begin() as session:
        repo = WalletRepository(session)
        await repo.save(enabled)
        await repo.save(disabled)

    event = make_event("tx-1", NOW)
    provider = FakeWalletIntelligenceProvider(
        activity={
            "solana:abc123": [event],
            "solana:def456": [make_event("tx-should-not-sync", NOW)],
        }
    )
    service = WalletMonitoringService(provider=provider, sessions=sessions)

    outcomes = await service.sync_all_enabled_wallets(NOW - timedelta(days=1))
    assert len(outcomes) == 1
    assert outcomes[0].chain == "solana"
    assert outcomes[0].address == "abc123"
    assert len(outcomes[0].new_events) == 1
    assert outcomes[0].error is None

    async with sessions() as session:
        disabled_events = await WalletActivityRepository(session).list_for_wallet(
            "solana", "def456"
        )
    assert disabled_events == ()


async def test_sync_all_enabled_wallets_records_one_wallets_failure_without_aborting_the_rest(
    sessions,
) -> None:
    good = make_wallet(address="abc123")
    bad = make_wallet(address="broken")
    async with sessions.begin() as session:
        repo = WalletRepository(session)
        await repo.save(good)
        await repo.save(bad)

    class RaisingProvider:
        async def fetch_wallet_activity(self, chain: str, address: str, since: datetime):
            if address == "broken":
                raise RuntimeError("provider outage")
            return [make_event("tx-1", NOW)]

        async def fetch_wallet_labels(self, chain: str, address: str):
            return ()

    service = WalletMonitoringService(provider=RaisingProvider(), sessions=sessions)
    outcomes = await service.sync_all_enabled_wallets(NOW - timedelta(days=1))

    by_address = {o.address: o for o in outcomes}
    assert by_address["abc123"].error is None
    assert len(by_address["abc123"].new_events) == 1
    assert by_address["broken"].error == "provider outage"
    assert by_address["broken"].new_events == ()
