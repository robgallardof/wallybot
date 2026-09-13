import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.wallet_activity import OnChainActionType
from wallybot.domain.whale_flow import WhaleTransferSignal
from wallybot.infrastructure.whale_flow_repository import WhaleTransferRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_whale_flow_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE whale_transfer_signals CASCADE")
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


def test_whale_flow_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/whale-flow").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker.begin() as session:
        await WhaleTransferRepository(session).save(
            WhaleTransferSignal(
                wallet_id="solana:whale-1",
                chain="solana",
                token="BONK",
                action=OnChainActionType.TRANSFER,
                amount=Decimal("1000000"),
                value_usd=Decimal("500000"),
                threshold_usd=Decimal("100000"),
                occurred_at=NOW,
                reasons=("value_usd 500000 meets threshold 100000",),
            )
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_whale_flow_route_serves_latest_signals(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/whale-flow")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["wallet_id"] == "solana:whale-1"
    assert rows[0]["token"] == "BONK"
    assert rows[0]["value_usd"] == "500000"


def test_whale_flow_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/intelligence/whale-flow")
    assert response.status_code == 200
    assert response.json()["rows"] == []
