import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.relationship import (
    NodeReference,
    NodeReferenceType,
    Relationship,
    RelationshipType,
)
from wallybot.infrastructure.relationship_repository import RelationshipRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_relationship(**overrides: Any) -> Relationship:
    fields: dict[str, Any] = {
        "id": "rel-1",
        "source": NodeReference(NodeReferenceType.WALLET, "ethereum:0xabc"),
        "relationship_type": RelationshipType.TRANSFERRED_TO,
        "target": NodeReference(NodeReferenceType.WALLET, "ethereum:0xdef"),
        "attribution": Attribution(
            source="arkham",
            source_entity_id=None,
            confidence=Decimal("0.7"),
            evidence="on-chain transfer observed",
            verification_status=VerificationStatus.UNVERIFIED,
            observed_at=NOW,
        ),
        "created_at": NOW,
    }
    fields.update(overrides)
    return Relationship(**fields)


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_relationship_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE relationships CASCADE")
    yield


async def test_relationship_round_trips(sessions) -> None:
    relationship = make_relationship()
    async with sessions.begin() as session:
        await RelationshipRepository(session).save(relationship)

    async with sessions() as session:
        loaded = await RelationshipRepository(session).get("rel-1")
    assert loaded is not None
    assert loaded.relationship_type is RelationshipType.TRANSFERRED_TO
    assert loaded.source.node_id == "ethereum:0xabc"
    assert loaded.attribution.source == "arkham"


async def test_saving_a_duplicate_relationship_id_is_rejected(sessions) -> None:
    relationship = make_relationship()
    async with sessions.begin() as session:
        await RelationshipRepository(session).save(relationship)

    with pytest.raises(ValueError, match="already exists"):
        async with sessions.begin() as session:
            await RelationshipRepository(session).save(relationship)


async def test_find_by_node_returns_relationships_on_either_side(sessions) -> None:
    outgoing = make_relationship(id="rel-out")
    incoming = make_relationship(
        id="rel-in",
        source=NodeReference(NodeReferenceType.ENTITY, "entity-1"),
        relationship_type=RelationshipType.CONTROLS,
        target=NodeReference(NodeReferenceType.WALLET, "ethereum:0xabc"),
    )
    async with sessions.begin() as session:
        repo = RelationshipRepository(session)
        await repo.save(outgoing)
        await repo.save(incoming)

    async with sessions() as session:
        found = await RelationshipRepository(session).find_by_node(
            NodeReferenceType.WALLET, "ethereum:0xabc"
        )
    assert {r.id for r in found} == {"rel-out", "rel-in"}


async def test_find_by_node_returns_nothing_for_an_unrelated_node(sessions) -> None:
    async with sessions.begin() as session:
        await RelationshipRepository(session).save(make_relationship())

    async with sessions() as session:
        found = await RelationshipRepository(session).find_by_node(
            NodeReferenceType.WALLET, "ethereum:0xdoesnotexist"
        )
    assert found == ()
