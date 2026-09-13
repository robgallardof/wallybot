import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.token_risk import TokenRiskScore, TokenRiskStatus
from wallybot.infrastructure.token_risk_repository import TokenRiskScoreRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
CHAIN = "solana"
TOKEN_ID = "BONK"


def make_scored(computed_at: datetime, risk_score: str = "25") -> TokenRiskScore:
    return TokenRiskScore(
        token_id=TOKEN_ID,
        chain=CHAIN,
        version=1,
        status=TokenRiskStatus.SCORED,
        risk_score=Decimal(risk_score),
        reasons=("mint authority is still active", "not evaluated: holder_concentration"),
        computed_at=computed_at,
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_token_risk_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE token_risk_scores CASCADE")
    yield


async def test_a_saved_score_round_trips(sessions) -> None:
    score = make_scored(NOW)
    async with sessions.begin() as session:
        await TokenRiskScoreRepository(session).save(score)

    async with sessions() as session:
        latest = await TokenRiskScoreRepository(session).latest(CHAIN, TOKEN_ID)
    assert latest is not None
    assert latest.risk_score == score.risk_score
    assert latest.reasons == score.reasons


async def test_saving_a_second_score_never_overwrites_the_first(sessions) -> None:
    first = make_scored(NOW - timedelta(days=1), risk_score="10")
    second = make_scored(NOW, risk_score="60")
    async with sessions.begin() as session:
        repo = TokenRiskScoreRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        repo = TokenRiskScoreRepository(session)
        history = await repo.history(CHAIN, TOKEN_ID)
        latest = await repo.latest(CHAIN, TOKEN_ID)

    assert len(history) == 2
    assert [s.risk_score for s in history] == [Decimal("10"), Decimal("60")]
    assert latest is not None
    assert latest.risk_score == Decimal("60")


async def test_an_insufficient_data_score_round_trips_with_no_risk_score(sessions) -> None:
    score = TokenRiskScore(
        token_id=TOKEN_ID,
        chain=CHAIN,
        version=1,
        status=TokenRiskStatus.INSUFFICIENT_DATA,
        risk_score=None,
        reasons=("the provider reported no security checks for this token",),
        computed_at=NOW,
    )
    async with sessions.begin() as session:
        await TokenRiskScoreRepository(session).save(score)

    async with sessions() as session:
        latest = await TokenRiskScoreRepository(session).latest(CHAIN, TOKEN_ID)
    assert latest is not None
    assert latest.status is TokenRiskStatus.INSUFFICIENT_DATA
    assert latest.risk_score is None
