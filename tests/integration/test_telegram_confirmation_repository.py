import asyncio
import sys
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.telegram_confirmation import CONFIRMATION_TTL, TelegramAction
from wallybot.infrastructure.telegram_confirmation_repository import TelegramConfirmationRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class SequentialIds:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"conf{self.counter}"


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
def _reset_telegram_confirmations(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE telegram_confirmations CASCADE")
    yield


async def test_a_created_confirmation_is_pending_and_listed(sessions) -> None:
    async with sessions() as session:
        repo = TelegramConfirmationRepository(session)
        confirmation = await repo.create(TelegramAction.PAUSE, NOW, SequentialIds())
        await session.commit()

    async with sessions() as session:
        pending = await TelegramConfirmationRepository(session).list_pending(NOW)
    assert len(pending) == 1
    assert pending[0].confirmation_id == confirmation.confirmation_id
    assert pending[0].action is TelegramAction.PAUSE
    assert pending[0].expires_at == NOW + CONFIRMATION_TTL


async def test_confirming_a_pending_confirmation_removes_it_from_the_pending_list(
    sessions,
) -> None:
    async with sessions() as session:
        repo = TelegramConfirmationRepository(session)
        confirmation = await repo.create(TelegramAction.RESUME, NOW, SequentialIds())
        await session.commit()

    async with sessions() as session:
        confirmed = await TelegramConfirmationRepository(session).confirm(
            confirmation.confirmation_id, "admin-1", NOW + timedelta(minutes=1)
        )
        await session.commit()
    assert confirmed is True

    async with sessions() as session:
        repo = TelegramConfirmationRepository(session)
        pending = await repo.list_pending(NOW + timedelta(minutes=1))
        stored = await repo.get(confirmation.confirmation_id)
    assert pending == ()
    assert stored is not None
    assert stored.confirmed_by == "admin-1"
    assert stored.is_confirmed is True


async def test_confirming_twice_only_succeeds_the_first_time(sessions) -> None:
    async with sessions() as session:
        repo = TelegramConfirmationRepository(session)
        confirmation = await repo.create(TelegramAction.PAUSE, NOW, SequentialIds())
        await session.commit()

    async with sessions() as session:
        first = await TelegramConfirmationRepository(session).confirm(
            confirmation.confirmation_id, "admin-1", NOW + timedelta(minutes=1)
        )
        await session.commit()
    async with sessions() as session:
        second = await TelegramConfirmationRepository(session).confirm(
            confirmation.confirmation_id, "admin-2", NOW + timedelta(minutes=2)
        )
        await session.commit()
    assert first is True
    assert second is False


async def test_an_expired_confirmation_cannot_be_confirmed_or_listed_as_pending(sessions) -> None:
    async with sessions() as session:
        repo = TelegramConfirmationRepository(session)
        confirmation = await repo.create(TelegramAction.PAUSE, NOW, SequentialIds())
        await session.commit()

    past_expiry = NOW + CONFIRMATION_TTL + timedelta(seconds=1)
    async with sessions() as session:
        pending = await TelegramConfirmationRepository(session).list_pending(past_expiry)
    assert pending == ()

    async with sessions() as session:
        confirmed = await TelegramConfirmationRepository(session).confirm(
            confirmation.confirmation_id, "admin-1", past_expiry
        )
        await session.commit()
    assert confirmed is False


async def test_confirming_an_unknown_confirmation_is_a_no_op(sessions) -> None:
    async with sessions() as session:
        confirmed = await TelegramConfirmationRepository(session).confirm(
            "does-not-exist", "admin-1", NOW
        )
        await session.commit()
    assert confirmed is False
