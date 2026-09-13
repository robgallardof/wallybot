import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.price_consensus import PriceConsensusResult, PriceConsensusStatus
from wallybot.infrastructure.price_consensus_repository import PriceConsensusRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
INSTRUMENT = "BTC/USD"


def make_consensus(computed_at: datetime, price: str = "50005") -> PriceConsensusResult:
    return PriceConsensusResult(
        instrument_id=INSTRUMENT,
        status=PriceConsensusStatus.CONSENSUS,
        consensus_price=Decimal(price),
        included_sources=("kraken", "coinbase"),
        excluded_sources=(),
        reasons=("2 of 2 quote(s) included after staleness/outlier filtering",),
        computed_at=computed_at,
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE price_consensus_results CASCADE")
    yield


async def test_a_saved_result_round_trips(sessions) -> None:
    result = make_consensus(NOW)
    async with sessions.begin() as session:
        await PriceConsensusRepository(session).save(result)

    async with sessions() as session:
        latest = await PriceConsensusRepository(session).latest(INSTRUMENT)
    assert latest is not None
    assert latest.consensus_price == result.consensus_price
    assert latest.included_sources == result.included_sources


async def test_saving_a_second_result_never_overwrites_the_first(sessions) -> None:
    first = make_consensus(NOW - timedelta(minutes=5), price="49990")
    second = make_consensus(NOW, price="50010")
    async with sessions.begin() as session:
        repo = PriceConsensusRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        history = await PriceConsensusRepository(session).history(INSTRUMENT)

    assert len(history) == 2
    assert [r.consensus_price for r in history] == [Decimal("49990"), Decimal("50010")]


async def test_an_insufficient_data_result_round_trips_with_no_price(sessions) -> None:
    result = PriceConsensusResult(
        instrument_id=INSTRUMENT,
        status=PriceConsensusStatus.INSUFFICIENT_DATA,
        consensus_price=None,
        included_sources=(),
        excluded_sources=("kraken",),
        reasons=("only 1 fresh quote(s) within 0:05:00, need at least 2",),
        computed_at=NOW,
    )
    async with sessions.begin() as session:
        await PriceConsensusRepository(session).save(result)

    async with sessions() as session:
        latest = await PriceConsensusRepository(session).latest(INSTRUMENT)
    assert latest is not None
    assert latest.status is PriceConsensusStatus.INSUFFICIENT_DATA
    assert latest.consensus_price is None
