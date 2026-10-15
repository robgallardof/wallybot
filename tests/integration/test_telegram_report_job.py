import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.telegram_report_job import run_telegram_report_tick
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.telegram_report_repository import TelegramReportRepository
from wallybot.security.crypto import Crypto

pytestmark = pytest.mark.integration

ACCOUNT_ID = "paper:report-test-user"
# A Thursday, so "start of week" (Monday) and "start of day" differ -- exercises both period
# windows distinctly rather than accidentally aliasing them.
NOW = datetime(2026, 1, 8, 15, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        self.calls.append((url, form))


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
            "enabled = false WHERE id = 1"
        )
        connection.execute("TRUNCATE telegram_reports")
        connection.execute("TRUNCATE equity_snapshots, fills, order_intents, breakers CASCADE")
    yield


async def _configure_telegram(sessions, crypto) -> None:
    encrypted = crypto.encrypt("bot-secret")
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(encrypted, 42, True)


async def test_sends_one_daily_and_one_weekly_report_on_the_first_tick(sessions, crypto) -> None:
    await _configure_telegram(sessions, crypto)
    transport = FakeTransport()

    await run_telegram_report_tick(
        sessions, crypto, transport, NotificationThrottle(), ACCOUNT_ID, "PAPER", NOW
    )

    assert len(transport.calls) == 2
    texts = [form["text"] for _, form in transport.calls]
    assert any("Daily report" in text for text in texts)
    assert any("Weekly report" in text for text in texts)
    assert any("No equity snapshot recorded" in text for text in texts)
    assert any("Benchmarks: not available" in text for text in texts)


async def test_a_second_tick_the_same_day_does_not_resend_the_daily_report(
    sessions, crypto
) -> None:
    await _configure_telegram(sessions, crypto)
    transport = FakeTransport()
    throttle = NotificationThrottle()

    await run_telegram_report_tick(sessions, crypto, transport, throttle, ACCOUNT_ID, "PAPER", NOW)
    transport.calls.clear()
    await run_telegram_report_tick(
        sessions, crypto, transport, throttle, ACCOUNT_ID, "PAPER", NOW + timedelta(hours=1)
    )

    assert transport.calls == []


async def test_a_tick_the_next_day_resends_only_the_daily_report(sessions, crypto) -> None:
    await _configure_telegram(sessions, crypto)
    transport = FakeTransport()
    throttle = NotificationThrottle()

    await run_telegram_report_tick(sessions, crypto, transport, throttle, ACCOUNT_ID, "PAPER", NOW)
    transport.calls.clear()
    await run_telegram_report_tick(
        sessions, crypto, transport, throttle, ACCOUNT_ID, "PAPER", NOW + timedelta(days=1)
    )

    assert len(transport.calls) == 1
    assert "Daily report" in transport.calls[0][1]["text"]


async def test_disabled_telegram_still_advances_the_period_marker(sessions, crypto) -> None:
    # Telegram is deliberately left unconfigured -- dispatch_telegram_notification is then a
    # no-op, but run_telegram_report_tick's own marker must still advance so a later tick on the
    # same day does not keep recomputing the same report on every 30-minute poll.
    transport = FakeTransport()

    await run_telegram_report_tick(
        sessions, crypto, transport, NotificationThrottle(), ACCOUNT_ID, "PAPER", NOW
    )

    assert transport.calls == []
    async with sessions() as db:
        key = await TelegramReportRepository(db).last_sent_key("DAILY")
    assert key == "2026-01-08"


class PublicBenchmarks:
    def __init__(self, now=NOW):
        self.calls = []
        self.now = now

    async def fetch_candles(self, instrument, timeframe, since, limit):
        from wallybot.domain.market import Candle

        self.calls.append((instrument, timeframe, since, limit))
        prices = ("100", "110") if instrument.base == "BTC" else ("200", "160")
        rows = []
        for close, price in zip((since + timedelta(hours=1), self.now), prices, strict=True):
            value = Decimal(price)
            rows.append(
                Candle(
                    instrument,
                    "1h",
                    close - timedelta(hours=1),
                    close,
                    value,
                    value,
                    value,
                    value,
                    Decimal(1),
                    instrument.venue,
                    self.now,
                )
            )
        return rows


async def test_operator_report_observes_current_mode_instead_of_hardcoded_paper(
    client, settings, db, sessions, crypto
):
    from tests.integration.test_connection_routes import enroll

    enroll(client, settings)
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    db.execute("UPDATE control SET environment='OBSERVE'")
    await _configure_telegram(sessions, crypto)
    transport = FakeTransport()
    prices = PublicBenchmarks()
    await run_telegram_report_tick(
        sessions,
        crypto,
        transport,
        NotificationThrottle(),
        "paper:wrong",
        "PAPER",
        NOW,
        owner_id=owner,
        language="es",
        market_providers={"binance": prices},
    )
    assert len(transport.calls) == 2
    for _, form in transport.calls:
        assert "Modo: OBSERVE" in form["text"]
        assert "Moneda: USDT" in form["text"]
        assert "no verificada" in form["text"]
        assert "PENDING.md" not in form["text"] and "Fase" not in form["text"]

    assert len(prices.calls) == 4
    for _, form in transport.calls:
        assert "BTC: +10.00%" in form["text"]
        assert "ETH: -20.00%" in form["text"]
        assert "50/50 (sin rebalanceo): -5.00%" in form["text"]
        assert "sin comisiones" in form["text"]


async def test_midnight_report_uses_previous_closed_reference_period(sessions, crypto):
    await _configure_telegram(sessions, crypto)
    transport = FakeTransport()
    midnight = NOW.replace(hour=0) + timedelta(days=1)
    await run_telegram_report_tick(
        sessions,
        crypto,
        transport,
        NotificationThrottle(),
        ACCOUNT_ID,
        "PAPER",
        midnight,
        currency="USDT",
        language="es",
        market_providers={"binance": PublicBenchmarks(midnight)},
    )
    daily = next(form["text"] for _, form in transport.calls if "Informe diario" in form["text"])
    assert "BTC: +10.00%" in daily
    assert "2026-01-08T00:00:00+00:00 → 2026-01-09T00:00:00+00:00" in daily
