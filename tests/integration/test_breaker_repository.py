import asyncio
import sys
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.breaker import BreakerType
from wallybot.infrastructure.breaker_repository import BreakerRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_breakers(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE breakers CASCADE")
    yield


async def test_tripping_a_new_breaker_makes_it_active(sessions) -> None:
    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.DAILY_LOSS, "daily loss 0.03 at or beyond limit 0.02", NOW)
        await session.commit()

    async with sessions() as session:
        active = await BreakerRepository(session).list_active()
    assert len(active) == 1
    assert active[0].breaker_type is BreakerType.DAILY_LOSS
    assert active[0].active is True


async def test_tripping_an_already_active_breaker_keeps_the_original_reason_and_time(
    sessions,
) -> None:
    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.DAILY_LOSS, "first reason", NOW)
        await session.commit()

    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.DAILY_LOSS, "second reason", NOW + timedelta(hours=1))
        await session.commit()

    async with sessions() as session:
        active = await BreakerRepository(session).list_active()
    assert len(active) == 1
    assert active[0].reason == "first reason"
    assert active[0].tripped_at == NOW


async def test_clearing_a_tripped_breaker_deactivates_it(sessions) -> None:
    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.DRAWDOWN, "drawdown 0.15 at or beyond limit 0.10", NOW)
        await session.commit()

    async with sessions() as session:
        cleared = await BreakerRepository(session).clear(
            BreakerType.DRAWDOWN, "admin-1", NOW + timedelta(minutes=5)
        )
        await session.commit()
    assert cleared is True

    async with sessions() as session:
        active = await BreakerRepository(session).list_active()
        all_breakers = await BreakerRepository(session).list_all()
    assert active == ()
    assert len(all_breakers) == 1
    assert all_breakers[0].active is False
    assert all_breakers[0].cleared_by == "admin-1"


async def test_clearing_a_breaker_that_was_never_tripped_is_a_no_op(sessions) -> None:
    async with sessions() as session:
        cleared = await BreakerRepository(session).clear(BreakerType.WEEKLY_LOSS, "admin-1", NOW)
        await session.commit()
    assert cleared is False


async def test_a_breaker_can_be_re_tripped_after_being_cleared(sessions) -> None:
    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.RECONCILIATION, "first trip", NOW)
        await session.commit()
    async with sessions() as session:
        await BreakerRepository(session).clear(
            BreakerType.RECONCILIATION, "admin-1", NOW + timedelta(minutes=1)
        )
        await session.commit()

    async with sessions() as session:
        repo = BreakerRepository(session)
        await repo.trip(BreakerType.RECONCILIATION, "second trip", NOW + timedelta(hours=2))
        await session.commit()

    async with sessions() as session:
        active = await BreakerRepository(session).list_active()
    assert len(active) == 1
    assert active[0].reason == "second trip"
