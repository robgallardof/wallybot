import asyncio
import sys

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.security.crypto import Crypto

pytestmark = pytest.mark.integration

NOTIFICATION = Notification(NotificationSeverity.WARNING, "Bot paused", "Environment: PAPER.")


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class FakeTransport:
    def __init__(self, *, fails: bool = False) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self._fails = fails

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        if self._fails:
            raise ConnectionError("simulated network failure")
        self.calls.append((url, form))


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def crypto(settings):
    return Crypto(settings.encryption_key.get_secret_value())


@pytest.fixture(autouse=True)
def _reset_telegram_config(dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "UPDATE telegram_config SET encrypted_bot_token = NULL, chat_id = NULL, "
            "enabled = false WHERE id = 1"
        )
    yield


async def _configure(sessions, crypto, *, enabled: bool, chat_id: int | None, token: str | None):
    encrypted = crypto.encrypt(token) if token else None
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(encrypted, chat_id, enabled)


async def test_disabled_config_sends_nothing(sessions, crypto) -> None:
    await _configure(sessions, crypto, enabled=False, chat_id=42, token="bot-token")
    transport = FakeTransport()

    await dispatch_telegram_notification(sessions, crypto, transport, NOTIFICATION)

    assert transport.calls == []


async def test_enabled_without_chat_id_sends_nothing(sessions, crypto) -> None:
    await _configure(sessions, crypto, enabled=True, chat_id=None, token="bot-token")
    transport = FakeTransport()

    await dispatch_telegram_notification(sessions, crypto, transport, NOTIFICATION)

    assert transport.calls == []


async def test_enabled_and_configured_sends_the_decrypted_token_to_the_chat(
    sessions, crypto
) -> None:
    await _configure(sessions, crypto, enabled=True, chat_id=42, token="bot-secret")
    transport = FakeTransport()

    await dispatch_telegram_notification(sessions, crypto, transport, NOTIFICATION)

    assert transport.calls == [
        (
            "https://api.telegram.org/botbot-secret/sendMessage",
            {
                "chat_id": "42",
                "text": "[WARNING] Bot paused\nEnvironment: PAPER.",
                "disable_web_page_preview": "true",
            },
        )
    ]


async def test_a_transport_failure_is_swallowed_not_raised(sessions, crypto) -> None:
    await _configure(sessions, crypto, enabled=True, chat_id=42, token="bot-secret")
    transport = FakeTransport(fails=True)

    await dispatch_telegram_notification(sessions, crypto, transport, NOTIFICATION)  # no raise
