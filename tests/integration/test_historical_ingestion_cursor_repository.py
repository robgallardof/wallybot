import asyncio
import sys
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.infrastructure.historical_ingestion_cursor_repository import (
    HistoricalIngestionCursorRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_cursor_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE historical_ingestion_cursors")
    yield


async def test_get_returns_none_when_no_cursor_exists(sessions) -> None:
    repository = HistoricalIngestionCursorRepository(sessions)
    assert await repository.get("kraken:SPOT:BTC/USD", "1h") is None


async def test_set_then_get_round_trips(sessions) -> None:
    repository = HistoricalIngestionCursorRepository(sessions)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    await repository.set("kraken:SPOT:BTC/USD", "1h", at)
    assert await repository.get("kraken:SPOT:BTC/USD", "1h") == at


async def test_set_overwrites_a_later_cursor_value(sessions) -> None:
    repository = HistoricalIngestionCursorRepository(sessions)
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = first + timedelta(hours=1)
    await repository.set("kraken:SPOT:BTC/USD", "1h", first)
    await repository.set("kraken:SPOT:BTC/USD", "1h", second)
    assert await repository.get("kraken:SPOT:BTC/USD", "1h") == second


async def test_set_never_moves_the_cursor_backwards(sessions) -> None:
    repository = HistoricalIngestionCursorRepository(sessions)
    later = datetime(2026, 1, 2, tzinfo=UTC)
    earlier = later - timedelta(hours=1)
    await repository.set("kraken:SPOT:BTC/USD", "1h", later)
    await repository.set("kraken:SPOT:BTC/USD", "1h", earlier)
    assert await repository.get("kraken:SPOT:BTC/USD", "1h") == later


async def test_cursors_are_independent_per_timeframe(sessions) -> None:
    repository = HistoricalIngestionCursorRepository(sessions)
    hourly = datetime(2026, 1, 1, tzinfo=UTC)
    daily = datetime(2026, 1, 2, tzinfo=UTC)
    await repository.set("kraken:SPOT:BTC/USD", "1h", hourly)
    await repository.set("kraken:SPOT:BTC/USD", "1d", daily)
    assert await repository.get("kraken:SPOT:BTC/USD", "1h") == hourly
    assert await repository.get("kraken:SPOT:BTC/USD", "1d") == daily
