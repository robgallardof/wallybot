import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pyotp
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet import Wallet
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.infrastructure.wallet_activity_repository import WalletActivityRepository
from wallybot.infrastructure.wallet_repository import WalletRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 10, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _reset_wallet_activity_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE wallet_activity_events, wallet_attributions, wallets CASCADE")
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


def test_wallet_activity_route_requires_auth(client) -> None:
    assert client.get("/api/intelligence/wallet-activity").status_code == 401


async def _seed_async(dependencies) -> None:
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    attribution = Attribution(
        source="helius",
        source_entity_id=None,
        confidence=Decimal("0.9"),
        evidence="on-chain swap transaction",
        verification_status=VerificationStatus.VERIFIED,
        observed_at=NOW,
    )
    async with maker.begin() as session:
        await WalletRepository(session).save(
            Wallet(
                address="abc123",
                chain="solana",
                entity_id=None,
                alias=None,
                labels=(),
                tags=(),
                confidence=Decimal("0.7"),
                trust_score=Decimal("0.6"),
                risk_score=Decimal("0.1"),
                enabled=True,
                influence_weight=Decimal("0.3"),
                max_signal_weight=Decimal("0.2"),
                max_allocation=None,
                min_transaction_value=Decimal("0"),
                attributions=(attribution,),
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await WalletActivityRepository(session).save(
            "solana",
            "abc123",
            WalletActivityEvent(
                wallet_id="solana:abc123",
                chain="solana",
                transaction_hash="tx-1",
                token="SOL",
                action=OnChainActionType.SWAP,
                amount=Decimal("1"),
                value_usd=Decimal("150"),
                price=Decimal("150"),
                liquidity_usd=Decimal("500000"),
                occurred_at=NOW,
                attribution=attribution,
            ),
        )
    await engine.dispose()


def _seed(dependencies) -> None:
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(_seed_async(dependencies), loop_factory=loop_factory)


def test_wallet_activity_route_serves_recent_events(client, settings, dependencies) -> None:
    _seed(dependencies)
    enroll(client, settings)

    response = client.get("/api/intelligence/wallet-activity")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["wallet_id"] == "solana:abc123"
    assert rows[0]["token"] == "SOL"
    assert rows[0]["action"] == "SWAP"


def test_wallet_activity_route_returns_empty_list_with_no_data(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/intelligence/wallet-activity")
    assert response.status_code == 200
    assert response.json()["rows"] == []
