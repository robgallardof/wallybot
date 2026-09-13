import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.provider_reliability import (
    ProviderReliabilitySnapshot,
    ProviderReliabilityStatus,
)
from wallybot.infrastructure.provider_reliability_repository import ProviderReliabilityRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
PROVIDER = "kraken"


def make_healthy(computed_at: datetime) -> ProviderReliabilitySnapshot:
    return ProviderReliabilitySnapshot(
        provider=PROVIDER,
        status=ProviderReliabilityStatus.HEALTHY,
        call_count=10,
        error_rate=Decimal("0"),
        average_latency_ms=Decimal("50"),
        seconds_since_last_success=Decimal("1"),
        computed_at=computed_at,
        reasons=("error rate 0% over 10 calls", "not evaluated: rate_limit_pressure"),
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE provider_reliability_snapshots CASCADE")
    yield


async def test_a_saved_snapshot_round_trips(sessions) -> None:
    snapshot = make_healthy(NOW)
    async with sessions.begin() as session:
        await ProviderReliabilityRepository(session).save(snapshot)

    async with sessions() as session:
        latest = await ProviderReliabilityRepository(session).latest(PROVIDER)
    assert latest is not None
    assert latest.status is ProviderReliabilityStatus.HEALTHY
    assert latest.reasons == snapshot.reasons


async def test_saving_a_second_snapshot_never_overwrites_the_first(sessions) -> None:
    first = make_healthy(NOW - timedelta(hours=1))
    second = make_healthy(NOW)
    async with sessions.begin() as session:
        repo = ProviderReliabilityRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        history = await ProviderReliabilityRepository(session).history(PROVIDER)

    assert len(history) == 2


async def test_an_insufficient_data_snapshot_round_trips_with_no_metrics(sessions) -> None:
    snapshot = ProviderReliabilitySnapshot(
        provider=PROVIDER,
        status=ProviderReliabilityStatus.INSUFFICIENT_DATA,
        call_count=2,
        error_rate=None,
        average_latency_ms=None,
        seconds_since_last_success=None,
        computed_at=NOW,
        reasons=("only 2 call(s) observed, need at least 5",),
    )
    async with sessions.begin() as session:
        await ProviderReliabilityRepository(session).save(snapshot)

    async with sessions() as session:
        latest = await ProviderReliabilityRepository(session).latest(PROVIDER)
    assert latest is not None
    assert latest.status is ProviderReliabilityStatus.INSUFFICIENT_DATA
    assert latest.error_rate is None
