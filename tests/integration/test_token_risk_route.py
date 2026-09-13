import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.token_risk import TokenRiskScore, TokenRiskStatus
from wallybot.infrastructure.token_risk_repository import TokenRiskScoreRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_token_risk_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE token_risk_scores CASCADE")
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


def test_token_risk_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/token-risk").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker.begin() as session:
        repo = TokenRiskScoreRepository(session)
        await repo.save(
            TokenRiskScore(
                token_id="rug-coin",
                chain="solana",
                version=1,
                status=TokenRiskStatus.SCORED,
                risk_score=Decimal("85"),
                reasons=("mint_authority_active",),
                computed_at=NOW,
            )
        )
        await repo.save(
            TokenRiskScore(
                token_id="unknown-token",
                chain="solana",
                version=1,
                status=TokenRiskStatus.INSUFFICIENT_DATA,
                risk_score=None,
                reasons=("no security provider data",),
                computed_at=NOW,
            )
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_token_risk_route_serves_latest_scores(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/token-risk")
    assert response.status_code == 200
    rows = {row["token_id"]: row for row in response.json()["rows"]}
    assert rows["rug-coin"]["status"] == "SCORED"
    assert rows["rug-coin"]["risk_score"] == "85"
    assert rows["unknown-token"]["status"] == "INSUFFICIENT_DATA"
    assert rows["unknown-token"]["risk_score"] is None


def test_token_risk_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/intelligence/token-risk")
    assert response.status_code == 200
    assert response.json()["rows"] == []
