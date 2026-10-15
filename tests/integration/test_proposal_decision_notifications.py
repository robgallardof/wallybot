"""Proposal decisions are committed before their optional Telegram notification."""

from datetime import UTC, datetime, timedelta
from functools import partial

import pyotp
import pytest
from psycopg.types.json import Jsonb

from tests.integration.test_proposal_execution import INSTRUMENT, ControlledProvider
from wallybot.application.execution_service import ExecutionService
from wallybot.application.proposal_execution import PaperAiExecution
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.system_clock import SystemClock

pytestmark = pytest.mark.integration


class FakeTelegramTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        self.calls.append((url, form))


def _enroll(client, settings) -> None:
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    started = client.post("/api/auth/setup/start", json=body)
    assert started.status_code == 200, started.text
    enrollment = started.json()
    finished = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finished.status_code == 200, finished.text


def _insert_pending_proposal(
    db, owner_id: str, proposal_id: str = "proposal-approved", age=timedelta(minutes=1)
) -> None:
    now = datetime.now(UTC)
    db.execute(
        """
        INSERT INTO trade_proposals (
            proposal_id, venue, base, quote, direction, strategy_id, confidence,
            suggested_allocation_pct, entry_price, stop_price, take_profit_price,
            time_horizon_seconds, signal_ttl_seconds, reasons, risks, supporting_signal_ids,
            invalidating_conditions, source_event_ids, model_id, prompt_version, as_of, owner_id
        ) VALUES (
            %s, 'kraken', 'BTC', 'USD', 'LONG', 'ai-consensus', 0.8,
            0.05, 50000, 48000, 55000, 86400, 3600, %s, %s, %s, %s, %s,
            'consensus:codex+claude', 'consensus/v1', %s, %s
        )
        """,
        (
            proposal_id,
            Jsonb(["analysts agree"]),
            Jsonb(["volatility"]),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            now - age,
            owner_id,
        ),
    )


def test_approval_commits_then_sends_an_informational_telegram_context(
    client, settings, db
) -> None:
    _enroll(client, settings)
    db.execute("UPDATE control SET environment = 'OBSERVE'")
    csrf = client.get("/api/auth/me").json()["csrf"]
    owner_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    _insert_pending_proposal(db, owner_id)
    configured = client.post(
        "/api/telegram",
        json={"bot_token": "123456:decision-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert configured.status_code == 200, configured.text
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport

    response = client.post(
        "/api/proposals/proposal-approved/approve", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"
    assert (
        db.execute(
            "SELECT decision_status FROM trade_proposals WHERE proposal_id = 'proposal-approved'"
        ).fetchone()[0]
        == "APPROVED"
    )
    assert len(transport.calls) == 1
    assert "proposal approved" in transport.calls[0][1]["text"]
    assert "BUY / Comprar BTC/USD" in transport.calls[0][1]["text"]
    assert "Recorded operator decision" in transport.calls[0][1]["text"]
    # OBSERVE is the default: the approval is recorded, but no order can exist.
    assert response.json()["execution_status"] == "OBSERVE_ONLY"
    assert "No order was created" in transport.calls[0][1]["text"]
    stored = db.execute(
        "SELECT execution_status, execution_order_id FROM trade_proposals "
        "WHERE proposal_id = 'proposal-approved'"
    ).fetchone()
    assert stored == ("OBSERVE_ONLY", None)
    assert (
        db.execute(
            "SELECT count(*) FROM order_intents WHERE account_id = %s",
            (f"paper-ai:{owner_id}",),
        ).fetchone()[0]
        == 0
    )


def test_an_expired_proposal_cannot_be_approved(client, settings, db) -> None:
    _enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    owner_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    _insert_pending_proposal(db, owner_id, "proposal-expired", timedelta(hours=2))

    response = client.post(
        "/api/proposals/proposal-expired/approve", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Proposal expired"
    assert (
        db.execute(
            "SELECT decision_status FROM trade_proposals WHERE proposal_id = 'proposal-expired'"
        ).fetchone()[0]
        == "PENDING"
    )
    listed_response = client.get("/api/proposals")
    assert listed_response.status_code == 200, listed_response.text
    listed = listed_response.json()["rows"]
    assert listed[0]["expires_at"] < datetime.now(UTC).isoformat()


def test_a_paper_approval_revalidates_and_fills_on_the_ai_account(client, settings, db) -> None:
    _enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    owner_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    db.execute("DELETE FROM order_intents WHERE account_id = %s", (f"paper-ai:{owner_id}",))
    # Breakers are global; other suites may leave some latched, which would (rightly) block.
    db.execute("DELETE FROM breakers")
    _insert_pending_proposal(db, owner_id, "proposal-paper")
    db.execute(
        "UPDATE trade_proposals SET venue = %s WHERE proposal_id = 'proposal-paper'",
        (INSTRUMENT.venue,),
    )
    db.execute("UPDATE control SET environment = 'PAPER'")
    # This existing fixture deliberately models a historical USD instrument.
    client.app.state.paper_cash_currency = "USD"
    funded = client.post(
        "/api/portfolio/ai/fund", json={"amount": "100000"}, headers={"X-CSRF-Token": csrf}
    )
    assert funded.status_code == 201, funded.text

    # Candle open times must sit on hour boundaries to pass the quality gate.
    provider = ControlledProvider(datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
    clock = SystemClock()
    sessions = client.app.state.sessions
    gateway = FakeExchange(clock=clock, market_data=provider)
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=clock)
    client.app.state.market_overview = partial(lambda **_: None, provider=provider)
    client.app.state.paper_ai = PaperAiExecution(
        gateway=gateway,
        execution=execution,
        reconciliation=ReconciliationService(execution=execution, sessions=sessions),
    )
    client.app.state.telegram_transport = FakeTelegramTransport()
    try:
        response = client.post(
            "/api/proposals/proposal-paper/approve", json={}, headers={"X-CSRF-Token": csrf}
        )
    finally:
        db.execute("UPDATE control SET environment = 'OBSERVE'")

    assert response.status_code == 200, response.text
    reasons = db.execute(
        "SELECT execution_reasons FROM trade_proposals WHERE proposal_id = 'proposal-paper'"
    ).fetchone()[0]
    assert response.json()["execution_status"] == "FILLED", reasons
    order = db.execute(
        "SELECT side, status, idempotency_key FROM order_intents WHERE account_id = %s",
        (f"paper-ai:{owner_id}",),
    ).fetchall()
    assert order == [("BUY", "FILLED", "proposal:proposal-paper")]
    listed = client.get("/api/proposals").json()["rows"][0]
    assert listed["execution"]["status"] == "FILLED"
    assert listed["simulation"] is not None
    # After a completed approval, the persisted fill survives rebuilding the account view.
    portfolio = client.get("/api/portfolio/ai").json()
    assert portfolio["proposal_history"][0]["proposal_id"] == "proposal-paper"
    assert portfolio["proposal_history"][0]["monitoring_status"] == "QUOTE_UNAVAILABLE"
    repeated = client.post(
        "/api/proposals/proposal-paper/approve", json={}, headers={"X-CSRF-Token": csrf}
    )
    assert repeated.status_code == 409
    assert client.get("/api/portfolio").json()["activity"] == []
    assert db.execute(
        "SELECT count(*) FROM order_intents WHERE account_id = %s", (f"paper-ai:{owner_id}",)
    ).fetchone() == (1,)
