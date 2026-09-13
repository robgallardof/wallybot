import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.wallet_activity import OnChainActionType
from wallybot.domain.whale_flow import WhaleTransferSignal
from wallybot.infrastructure.whale_flow_repository import WhaleTransferRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
WALLET_ID = "solana:whale1"


def make_signal(occurred_at: datetime, value_usd: str = "150000") -> WhaleTransferSignal:
    return WhaleTransferSignal(
        wallet_id=WALLET_ID,
        chain="solana",
        token="SOL",
        action=OnChainActionType.TRANSFER,
        amount=Decimal("1000"),
        value_usd=Decimal(value_usd),
        threshold_usd=Decimal("100000"),
        occurred_at=occurred_at,
        reasons=("TRANSFER of 1000 SOL ($150000) meets or exceeds the $100000 whale threshold",),
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_whale_transfer_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE whale_transfer_signals CASCADE")
    yield


async def test_a_saved_signal_round_trips(sessions) -> None:
    signal = make_signal(NOW)
    async with sessions.begin() as session:
        await WhaleTransferRepository(session).save(signal)

    async with sessions() as session:
        latest = await WhaleTransferRepository(session).latest()
    assert len(latest) == 1
    assert latest[0].value_usd == signal.value_usd
    assert latest[0].reasons == signal.reasons


async def test_saving_a_second_signal_never_overwrites_the_first(sessions) -> None:
    first = make_signal(NOW - timedelta(hours=1), value_usd="120000")
    second = make_signal(NOW, value_usd="200000")
    async with sessions.begin() as session:
        repo = WhaleTransferRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        history = await WhaleTransferRepository(session).history_for_wallet(WALLET_ID)

    assert len(history) == 2
    assert [s.value_usd for s in history] == [Decimal("120000"), Decimal("200000")]


async def test_history_for_wallet_only_returns_matching_wallet(sessions) -> None:
    this_wallet = make_signal(NOW)
    other_wallet = WhaleTransferSignal(
        wallet_id="solana:other",
        chain="solana",
        token="SOL",
        action=OnChainActionType.TRANSFER,
        amount=Decimal("500"),
        value_usd=Decimal("150000"),
        threshold_usd=Decimal("100000"),
        occurred_at=NOW,
        reasons=("x",),
    )
    async with sessions.begin() as session:
        repo = WhaleTransferRepository(session)
        await repo.save(this_wallet)
        await repo.save(other_wallet)

    async with sessions() as session:
        history = await WhaleTransferRepository(session).history_for_wallet(WALLET_ID)

    assert len(history) == 1
    assert history[0].wallet_id == WALLET_ID
