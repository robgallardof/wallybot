import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.ai_proposal_digest_job import run_ai_proposal_digest_tick
from wallybot.domain.ai_autonomy import AiAutonomyStatus
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal
from wallybot.infrastructure.ai_proposal_digest_repository import AiProposalDigestRepository
from wallybot.infrastructure.models import AiAutonomyControlRow, UserRow
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.trade_proposal_repository import TradeProposalRepository
from wallybot.security.crypto import Crypto

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 8, 15, 0, tzinfo=UTC)
OWNER_ID = "ai-digest-owner"
INSTRUMENT = Instrument(
    venue="kraken",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


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
            "TRUNCATE ai_proposal_digests, trade_proposals, users, telegram_config CASCADE"
        )
        connection.execute(
            "UPDATE ai_autonomy_control SET status = 'ENABLED', digest_interval_hours = 6"
        )
    yield


async def _configure_telegram(sessions, crypto) -> None:
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).upsert(crypto.encrypt("bot-secret"), 42, True)


async def _save_pending_proposal(
    sessions, proposal_id: str = "digest-proposal", as_of: datetime = NOW
) -> None:
    async with sessions.begin() as db:
        if await db.get(UserRow, OWNER_ID) is not None:
            await _save_proposal(db, proposal_id, as_of)
            return
        db.add(
            UserRow(
                id=OWNER_ID,
                username="digest-owner",
                password_hash="unused",
                totp_encrypted="unused",
                last_totp_step=-1,
                role="ADMIN",
                created_at=0,
            )
        )
        await db.flush()
        await _save_proposal(db, proposal_id, as_of)


async def _save_proposal(db, proposal_id: str, as_of: datetime) -> None:
    await TradeProposalRepository(db).save(
        TradeProposal(
            proposal_id=proposal_id,
            instrument=INSTRUMENT,
            direction=TradeDirection.LONG,
            strategy_id="ai-consensus",
            confidence=Decimal("0.8"),
            suggested_allocation_pct=Decimal("0.05"),
            entry_price=Decimal("50000"),
            stop_price=Decimal("48000"),
            take_profit_price=Decimal("55000"),
            time_horizon=timedelta(days=1),
            signal_ttl=timedelta(hours=1),
            reasons=("analysts agree",),
            risks=("volatility",),
            supporting_signal_ids=(),
            invalidating_conditions=(),
            source_event_ids=(),
            model_id="consensus:codex+claude",
            prompt_version="consensus/v1+v1",
            as_of=as_of,
        ),
        owner_id=OWNER_ID,
    )


async def test_new_pending_proposal_has_a_detailed_card(sessions, crypto) -> None:
    await _configure_telegram(sessions, crypto)
    await _save_pending_proposal(sessions)
    transport = FakeTransport()

    sent = await run_ai_proposal_digest_tick(
        sessions, crypto, transport, NotificationThrottle(), OWNER_ID, NOW + timedelta(minutes=1)
    )

    assert sent is True
    assert len(transport.calls) == 1
    assert "COMPRAR BTC/USD" in transport.calls[0][1]["text"]
    assert "Por qué: analysts agree" in transport.calls[0][1]["text"]
    assert "reply_markup" in transport.calls[0][1]
    async with sessions() as db:
        assert await AiProposalDigestRepository(db).last_sent_at(OWNER_ID) == NOW + timedelta(
            minutes=1
        )


async def test_digest_cadence_prevents_repeated_notifications(sessions, crypto) -> None:
    await _configure_telegram(sessions, crypto)
    await _save_pending_proposal(sessions)
    transport = FakeTransport()
    throttle = NotificationThrottle()

    await run_ai_proposal_digest_tick(sessions, crypto, transport, throttle, OWNER_ID, NOW)
    sent_again = await run_ai_proposal_digest_tick(
        sessions, crypto, transport, throttle, OWNER_ID, NOW + timedelta(hours=1)
    )

    assert sent_again is False
    assert len(transport.calls) == 1


async def test_disabled_analysis_does_not_send_a_digest(sessions, crypto) -> None:
    await _configure_telegram(sessions, crypto)
    await _save_pending_proposal(sessions)
    async with sessions.begin() as db:
        control = await db.get(AiAutonomyControlRow, 1)
        assert control is not None
        control.status = AiAutonomyStatus.DISABLED
    transport = FakeTransport()

    sent = await run_ai_proposal_digest_tick(
        sessions, crypto, transport, NotificationThrottle(), OWNER_ID, NOW
    )

    assert sent is False
    assert transport.calls == []


async def test_immediate_alert_ignores_the_digest_cadence_but_never_repeats(
    sessions, crypto
) -> None:
    await _configure_telegram(sessions, crypto)
    await _save_pending_proposal(sessions)
    transport = FakeTransport()
    throttle = NotificationThrottle()

    await run_ai_proposal_digest_tick(sessions, crypto, transport, throttle, OWNER_ID, NOW)
    await _save_pending_proposal(
        sessions, proposal_id="proposal-2", as_of=NOW + timedelta(minutes=5)
    )
    sent = await run_ai_proposal_digest_tick(
        sessions,
        crypto,
        transport,
        throttle,
        OWNER_ID,
        NOW + timedelta(minutes=6),
        immediate=True,
        web_origin="https://wally.example",
    )
    repeated = await run_ai_proposal_digest_tick(
        sessions, crypto, transport, throttle, OWNER_ID, NOW + timedelta(minutes=7), immediate=True
    )

    assert sent is True and repeated is False
    assert len(transport.calls) == 2
    assert "/approve proposal-2" in transport.calls[1][1]["text"]
    assert "https://wally.example/intelligence?proposal=proposal-2" in transport.calls[1][1]["text"]
