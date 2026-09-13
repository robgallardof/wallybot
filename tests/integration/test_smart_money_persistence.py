import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.smart_money import SmartMoneyScoreSnapshot, SmartMoneyStatus
from wallybot.infrastructure.smart_money_repository import SmartMoneyScoreRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
WALLET_ID = "solana:abc123"


def make_scored(computed_at: datetime, score: str = "72.5") -> SmartMoneyScoreSnapshot:
    return SmartMoneyScoreSnapshot(
        wallet_id=WALLET_ID,
        version=1,
        status=SmartMoneyStatus.SCORED,
        score=Decimal(score),
        trade_count=6,
        win_rate=Decimal("0.83"),
        realized_pnl_usd=Decimal("450"),
        wallet_age=timedelta(days=30),
        computed_at=computed_at,
        reasons=("win_rate=0.83, realized_pnl_usd=450 over 6 completed trades", "not evaluated: x"),
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_smart_money_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE smart_money_score_snapshots CASCADE")
    yield


async def test_a_saved_snapshot_round_trips(sessions) -> None:
    snapshot = make_scored(NOW)
    async with sessions.begin() as session:
        await SmartMoneyScoreRepository(session).save(snapshot)

    async with sessions() as session:
        latest = await SmartMoneyScoreRepository(session).latest(WALLET_ID)
    assert latest is not None
    assert latest.score == snapshot.score
    assert latest.wallet_age == snapshot.wallet_age
    assert latest.reasons == snapshot.reasons


async def test_saving_a_second_snapshot_never_overwrites_the_first(sessions) -> None:
    first = make_scored(NOW - timedelta(days=1), score="50")
    second = make_scored(NOW, score="80")
    async with sessions.begin() as session:
        repo = SmartMoneyScoreRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        repo = SmartMoneyScoreRepository(session)
        history = await repo.history(WALLET_ID)
        latest = await repo.latest(WALLET_ID)

    assert len(history) == 2
    assert [s.score for s in history] == [Decimal("50"), Decimal("80")]
    assert latest is not None
    assert latest.score == Decimal("80")


async def test_an_insufficient_data_snapshot_round_trips_with_no_score(sessions) -> None:
    snapshot = SmartMoneyScoreSnapshot(
        wallet_id=WALLET_ID,
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
    async with sessions.begin() as session:
        await SmartMoneyScoreRepository(session).save(snapshot)

    async with sessions() as session:
        latest = await SmartMoneyScoreRepository(session).latest(WALLET_ID)
    assert latest is not None
    assert latest.status is SmartMoneyStatus.INSUFFICIENT_DATA
    assert latest.score is None
    assert latest.wallet_age is None
