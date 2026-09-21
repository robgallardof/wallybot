import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.telegram_command_loop import run_telegram_command_tick
from wallybot.domain.equity import EquitySnapshot
from wallybot.domain.telegram_confirmation import TelegramAction
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.telegram_confirmation_repository import TelegramConfirmationRepository
from wallybot.security.crypto import Crypto, digest

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ALLOWED_CHAT_ID = 42


class SequentialIds:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"conf{self.counter}"


class FakeCommandTransport:
    def __init__(self, updates: list[dict]) -> None:
        self._updates = updates
        self.get_calls: list[tuple[str, dict[str, str]]] = []
        self.sent: list[tuple[str, dict[str, str]]] = []

    async def get_json(self, url: str, params: dict[str, str]) -> dict:
        self.get_calls.append((url, params))
        return {"ok": True, "result": self._updates}

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        self.sent.append((url, form))


def _message(update_id: int, chat_id: int, text: str) -> dict:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "text": text},
    }


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def crypto(settings):
    return Crypto(settings.encryption_key.get_secret_value())


@pytest.fixture(autouse=True)
def _reset(dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "UPDATE telegram_config SET encrypted_bot_token = NULL, chat_id = NULL, "
            "enabled = false, last_update_id = NULL, pairing_code_hash = NULL WHERE id = 1"
        )
        connection.execute("TRUNCATE telegram_confirmations CASCADE")
        connection.execute("UPDATE control SET status = 'RUNNING'")
    yield


async def _configure(sessions, crypto, *, chat_id: int = ALLOWED_CHAT_ID) -> None:
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(crypto.encrypt("bot-token"), chat_id, True)


async def test_disabled_config_polls_nothing(sessions, crypto) -> None:
    transport = FakeCommandTransport([])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)
    assert transport.get_calls == []


async def test_first_poll_only_establishes_a_baseline_without_executing_anything(
    sessions, crypto
) -> None:
    await _configure(sessions, crypto)
    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/status")])

    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert transport.sent == []
    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    assert config is not None
    assert config.last_update_id == 100


async def test_start_with_matching_one_time_code_binds_the_chat(sessions, crypto) -> None:
    pairing_code = "link_9qK-2"
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(
            crypto.encrypt("bot-token"),
            None,
            True,
            pairing_code_hash=digest(pairing_code),
            begin_pairing=True,
        )
    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, f"/start {pairing_code}")])

    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    assert config is not None
    assert config.chat_id == ALLOWED_CHAT_ID
    assert config.pairing_code_hash is None
    assert config.last_update_id == 100
    assert transport.sent[0][1]["chat_id"] == str(ALLOWED_CHAT_ID)


async def test_start_with_wrong_code_never_allowlists_a_chat(sessions, crypto) -> None:
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(
            crypto.encrypt("bot-token"),
            None,
            True,
            pairing_code_hash=digest("expected"),
            begin_pairing=True,
        )
    transport = FakeCommandTransport([_message(100, 999, "/start wrong")])

    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    assert config is not None
    assert config.chat_id is None
    assert config.pairing_code_hash is not None
    assert config.last_update_id == 100
    assert transport.sent == []


async def test_status_command_from_the_allowlisted_chat_gets_a_reply(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/status")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert len(transport.sent) == 1
    url, form = transport.sent[0]
    assert url.endswith("/sendMessage")
    assert form["chat_id"] == str(ALLOWED_CHAT_ID)
    assert "RUNNING" in form["text"]


async def test_help_command_lists_every_recognized_command(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/help")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert len(transport.sent) == 1
    reply = transport.sent[0][1]["text"]
    for command in ("/status", "/breakers", "/portfolio", "/pause", "/resume", "/help"):
        assert command in reply


async def test_commands_and_start_are_aliases_for_help_once_already_paired(
    sessions, crypto
) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport(
        [_message(100, ALLOWED_CHAT_ID, "/commands"), _message(101, ALLOWED_CHAT_ID, "/start")]
    )
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert len(transport.sent) == 2
    assert "/status" in transport.sent[0][1]["text"]
    assert "/status" in transport.sent[1][1]["text"]


async def test_a_message_from_an_unallowlisted_chat_is_ignored(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, 999, "/status")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert transport.sent == []


async def test_pause_creates_a_pending_confirmation_and_never_executes_directly(
    sessions, crypto
) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/pause")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    async with sessions() as db:
        pending = await TelegramConfirmationRepository(db).list_pending(NOW)
    assert len(pending) == 1
    assert pending[0].action is TelegramAction.PAUSE

    assert len(transport.sent) == 1
    assert "Confírmala en la web" in transport.sent[0][1]["text"]


async def test_pause_when_already_paused_replies_without_creating_a_confirmation(
    sessions, crypto, dependencies
) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("UPDATE control SET status = 'PAUSED'")

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/pause")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    async with sessions() as db:
        pending = await TelegramConfirmationRepository(db).list_pending(NOW)
    assert pending == ()
    assert "Ya está en estado" in transport.sent[0][1]["text"]


async def test_breakers_command_reports_no_active_breakers_by_default(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/breakers")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert "Sin breakers activos" in transport.sent[0][1]["text"]


async def test_portfolio_command_without_an_account_reports_unavailable(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/portfolio")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert "no disponible" in transport.sent[0][1]["text"]


async def test_portfolio_command_reports_the_latest_equity_snapshot(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)
        await EquitySnapshotRepository(db).save(
            EquitySnapshot(
                account_id="paper:admin-1",
                environment="PAPER",
                equity=Decimal("10500.00"),
                high_water_mark=Decimal("11000.00"),
                recorded_at=NOW,
            )
        )

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "/portfolio")])
    await run_telegram_command_tick(
        sessions, crypto, transport, SequentialIds(), "paper:admin-1", NOW
    )

    assert "10500.00" in transport.sent[0][1]["text"]
    assert "11000.00" in transport.sent[0][1]["text"]


async def test_an_unrecognized_message_gets_no_reply(sessions, crypto) -> None:
    await _configure(sessions, crypto)
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(99)

    transport = FakeCommandTransport([_message(100, ALLOWED_CHAT_ID, "hola")])
    await run_telegram_command_tick(sessions, crypto, transport, SequentialIds(), None, NOW)

    assert transport.sent == []
    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    assert config is not None
    assert config.last_update_id == 100
