import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
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

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_relationships_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE relationships CASCADE")
    yield


def enroll(client, settings):
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    result = client.post("/api/auth/setup/start", json=body)
    assert result.status_code == 200, result.text
    enrollment = result.json()
    finish = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finish.status_code == 200, finish.text
    return finish.json()


def test_entity_graph_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/entity-graph").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker.begin() as session:
        await RelationshipRepository(session).save(
            Relationship(
                id="rel-1",
                source=NodeReference(NodeReferenceType.WALLET, "solana:abc123"),
                relationship_type=RelationshipType.CONTROLS,
                target=NodeReference(NodeReferenceType.ENTITY, "entity-1"),
                attribution=Attribution(
                    source="helius",
                    source_entity_id=None,
                    confidence=Decimal("0.9"),
                    evidence="linked via a labeled deposit address",
                    verification_status=VerificationStatus.VERIFIED,
                    observed_at=NOW,
                ),
                created_at=NOW,
            )
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_entity_graph_route_serves_recent_relationships(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/entity-graph")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["source_id"] == "solana:abc123"
    assert rows[0]["relationship_type"] == "CONTROLS"
    assert rows[0]["target_id"] == "entity-1"


def test_entity_graph_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/intelligence/entity-graph")
    assert response.status_code == 200
    assert response.json()["rows"] == []
