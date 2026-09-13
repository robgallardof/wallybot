import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.smart_money import SmartMoneyScoreSnapshot, SmartMoneyStatus
from wallybot.infrastructure.smart_money_repository import SmartMoneyScoreRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_smart_money_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE smart_money_score_snapshots CASCADE")
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


def test_smart_money_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/smart-money").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker.begin() as session:
        repo = SmartMoneyScoreRepository(session)
        await repo.save(
            SmartMoneyScoreSnapshot(
                wallet_id="solana:scored-wallet",
                version=1,
                status=SmartMoneyStatus.SCORED,
                score=Decimal("72.5"),
                trade_count=6,
                win_rate=Decimal("0.83"),
                realized_pnl_usd=Decimal("450"),
                wallet_age=None,
                computed_at=NOW,
                reasons=("win_rate=0.83 over 6 completed trades",),
            )
        )
        await repo.save(
            SmartMoneyScoreSnapshot(
                wallet_id="solana:thin-wallet",
                version=1,
                status=SmartMoneyStatus.INSUFFICIENT_DATA,
                score=None,
                trade_count=2,
                win_rate=None,
                realized_pnl_usd=None,
                wallet_age=None,
                computed_at=NOW,
                reasons=("only 2 completed round trip(s), need at least 5",),
            )
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_smart_money_route_serves_latest_scores(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/smart-money")
    assert response.status_code == 200
    rows = {row["wallet_id"]: row for row in response.json()["rows"]}

    assert rows["solana:scored-wallet"]["status"] == "SCORED"
    assert rows["solana:scored-wallet"]["score"] == "72.5"
    assert rows["solana:thin-wallet"]["status"] == "INSUFFICIENT_DATA"
    assert rows["solana:thin-wallet"]["score"] is None


def test_smart_money_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/intelligence/smart-money")
    assert response.status_code == 200
    assert response.json()["rows"] == []
