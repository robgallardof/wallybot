import asyncio
import sys
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.infrastructure.telegram_report_repository import TelegramReportRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 8, 0, 0, tzinfo=UTC)


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
def _reset_telegram_reports(dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE telegram_reports")
    yield


async def test_a_period_with_no_prior_report_has_no_last_sent_key(sessions) -> None:
    async with sessions() as session:
        key = await TelegramReportRepository(session).last_sent_key("DAILY")

    assert key is None


async def test_marking_sent_makes_the_key_visible_to_a_later_read(sessions) -> None:
    async with sessions.begin() as session:
        await TelegramReportRepository(session).mark_sent("DAILY", "2026-01-08", NOW)

    async with sessions() as session:
        key = await TelegramReportRepository(session).last_sent_key("DAILY")

    assert key == "2026-01-08"


async def test_marking_sent_again_overwrites_the_previous_key(sessions) -> None:
    async with sessions.begin() as session:
        await TelegramReportRepository(session).mark_sent("DAILY", "2026-01-08", NOW)
    async with sessions.begin() as session:
        await TelegramReportRepository(session).mark_sent(
            "DAILY", "2026-01-09", NOW + timedelta(days=1)
        )

    async with sessions() as session:
        key = await TelegramReportRepository(session).last_sent_key("DAILY")

    assert key == "2026-01-09"


async def test_daily_and_weekly_periods_are_tracked_independently(sessions) -> None:
    async with sessions.begin() as session:
        await TelegramReportRepository(session).mark_sent("DAILY", "2026-01-08", NOW)

    async with sessions() as session:
        weekly_key = await TelegramReportRepository(session).last_sent_key("WEEKLY")

    assert weekly_key is None
