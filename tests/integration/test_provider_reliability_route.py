import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.provider_reliability import (
    ProviderReliabilitySnapshot,
    ProviderReliabilityStatus,
)
from wallybot.infrastructure.provider_reliability_repository import ProviderReliabilityRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE provider_reliability_snapshots CASCADE")
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


def test_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/provider-reliability").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker.begin() as session:
        await ProviderReliabilityRepository(session).save(
            ProviderReliabilitySnapshot(
                provider="kraken",
                status=ProviderReliabilityStatus.HEALTHY,
                call_count=100,
                error_rate=Decimal("0.01"),
                average_latency_ms=Decimal("120"),
                seconds_since_last_success=Decimal("5"),
                computed_at=NOW,
                reasons=("error_rate=0.01 below threshold",),
            )
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_route_serves_latest_snapshots(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/provider-reliability")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["provider"] == "kraken"
    assert rows[0]["status"] == "HEALTHY"
    assert rows[0]["error_rate"] == "0.01"


def test_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)
    response = client.get("/api/intelligence/provider-reliability")
    assert response.status_code == 200
    assert response.json()["rows"] == []
