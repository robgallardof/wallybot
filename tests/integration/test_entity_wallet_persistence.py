import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.entity import Attribution, Entity, EntityType, VerificationStatus
from wallybot.domain.wallet import MonitoringMode, Wallet, WalletCluster
from wallybot.infrastructure.entity_repository import EntityRepository
from wallybot.infrastructure.wallet_repository import WalletRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "arkham",
        "source_entity_id": "arkham-1",
        "confidence": Decimal("0.8"),
        "evidence": "labeled by Arkham entity intelligence",
        "verification_status": VerificationStatus.UNVERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_entity(**overrides: Any) -> Entity:
    fields: dict[str, Any] = {
        "id": "entity-1",
        "name": "Example Fund",
        "entity_type": EntityType.FUND,
        "aliases": ("Example",),
        "description": "A hypothetical fund used only in tests.",
        "enabled": True,
        "confidence": Decimal("0.9"),
        "trust_score": Decimal("0.7"),
        "risk_score": Decimal("0.2"),
        "influence_weight": Decimal("0.5"),
        "tags": ("fund",),
        "attributions": (make_attribution(),),
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return Entity(**fields)


def make_wallet(**overrides: Any) -> Wallet:
    fields: dict[str, Any] = {
        "address": "0xabc",
        "chain": "ethereum",
        "entity_id": None,
        "alias": None,
        "labels": ("smart_money",),
        "tags": (),
        "confidence": Decimal("0.7"),
        "trust_score": Decimal("0.6"),
        "risk_score": Decimal("0.1"),
        "enabled": True,
        "influence_weight": Decimal("0.3"),
        "max_signal_weight": Decimal("0.2"),
        "max_allocation": Decimal("1000"),
        "min_transaction_value": Decimal("100"),
        "attributions": (make_attribution(source="nansen", source_entity_id=None),),
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
def _reset_intelligence_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE wallet_cluster_members, wallet_clusters, wallet_attributions, wallets, "
            "entity_attributions, entities CASCADE"
        )
    yield


async def test_entity_round_trips_with_its_attribution(sessions) -> None:
    entity = make_entity()
    async with sessions.begin() as session:
        await EntityRepository(session).save(entity)

    async with sessions() as session:
        loaded = await EntityRepository(session).get("entity-1")
    assert loaded is not None
    assert loaded.name == entity.name
    assert loaded.entity_type is EntityType.FUND
    assert len(loaded.attributions) == 1
    assert loaded.attributions[0].source == "arkham"


async def test_saving_an_entity_twice_updates_summary_fields_without_duplicating_attributions(
    sessions,
) -> None:
    entity = make_entity()
    async with sessions.begin() as session:
        await EntityRepository(session).save(entity)

    updated = make_entity(trust_score=Decimal("0.95"), enabled=False)
    async with sessions.begin() as session:
        await EntityRepository(session).save(updated)

    async with sessions() as session:
        loaded = await EntityRepository(session).get("entity-1")
    assert loaded is not None
    assert loaded.trust_score == Decimal("0.95")
    assert loaded.enabled is False
    assert len(loaded.attributions) == 1  # same (source, source_entity_id, observed_at) claim


async def test_a_new_attribution_from_a_different_source_is_appended_not_replaced(sessions) -> None:
    entity = make_entity()
    async with sessions.begin() as session:
        await EntityRepository(session).save(entity)

    corroborated = make_entity(
        attributions=(
            make_attribution(),
            make_attribution(
                source="quiver",
                source_entity_id="quiver-1",
                verification_status=VerificationStatus.CORROBORATED,
            ),
        )
    )
    async with sessions.begin() as session:
        await EntityRepository(session).save(corroborated)

    async with sessions() as session:
        loaded = await EntityRepository(session).get("entity-1")
    assert loaded is not None
    assert {a.source for a in loaded.attributions} == {"arkham", "quiver"}


async def test_wallet_round_trips_and_defaults_to_observe(sessions) -> None:
    wallet = make_wallet()
    async with sessions.begin() as session:
        await WalletRepository(session).save(wallet)

    async with sessions() as session:
        loaded = await WalletRepository(session).get("ethereum", "0xabc")
    assert loaded is not None
    assert loaded.monitoring_mode is MonitoringMode.OBSERVE
    assert loaded.id == "ethereum:0xabc"
    assert len(loaded.attributions) == 1


async def test_wallet_can_reference_an_entity(sessions) -> None:
    entity = make_entity()
    async with sessions.begin() as session:
        await EntityRepository(session).save(entity)

    wallet = make_wallet(entity_id="entity-1")
    async with sessions.begin() as session:
        await WalletRepository(session).save(wallet)

    async with sessions() as session:
        loaded = await WalletRepository(session).get("ethereum", "0xabc")
    assert loaded is not None
    assert loaded.entity_id == "entity-1"


async def test_wallet_cluster_round_trips_and_is_insert_only(sessions) -> None:
    first_wallet = make_wallet(address="0xabc")
    second_wallet = make_wallet(address="0xdef")
    async with sessions.begin() as session:
        repo = WalletRepository(session)
        await repo.save(first_wallet)
        await repo.save(second_wallet)

    cluster = WalletCluster(
        id="cluster-1",
        entity_id=None,
        wallet_ids=("ethereum:0xabc", "ethereum:0xdef"),
        confidence=Decimal("0.75"),
        evidence="both wallets bought the same token within 30 minutes",
        created_at=NOW,
    )
    async with sessions.begin() as session:
        await WalletRepository(session).save_cluster(cluster)

    async with sessions() as session:
        loaded = await WalletRepository(session).get_cluster("cluster-1")
    assert loaded is not None
    assert set(loaded.wallet_ids) == {"ethereum:0xabc", "ethereum:0xdef"}

    with pytest.raises(ValueError, match="already exists"):
        async with sessions.begin() as session:
            await WalletRepository(session).save_cluster(cluster)
