from datetime import UTC, datetime, timedelta
from functools import partial

import pytest

from apps.api.proposal_routes import decide_from_telegram
from tests.integration.test_portfolio_route import enroll
from tests.integration.test_proposal_decision_notifications import _insert_pending_proposal
from tests.integration.test_telegram_command_loop import (
    FakeCommandTransport,
    SequentialIds,
    _message,
)
from wallybot.application.telegram_command_loop import run_telegram_command_tick

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("decision", ["approve", "reject", "simulate"])
def test_telegram_requests_open_review_without_consuming_approval(client, settings, db, decision):
    enroll(client, settings)
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    _insert_pending_proposal(db, owner, "review-proposal")
    encrypted = client.app.state.auth.crypto.encrypt("synthetic-bot-token")
    db.execute(
        "UPDATE telegram_config SET encrypted_bot_token=%s, chat_id=42, enabled=true, "
        "last_update_id=99 WHERE id=1",
        (encrypted,),
    )
    transport = FakeCommandTransport([_message(100, 42, f"/{decision} review-proposal", "en")])
    client.portal.call(
        partial(
            run_telegram_command_tick,
            client.app.state.sessions,
            client.app.state.auth.crypto,
            transport,
            SequentialIds(),
            f"paper:{owner}",
            datetime.now(UTC),
            owner_id=owner,
            web_origin="http://localhost:3333",
        )
    )
    reply = transport.sent[0][1]["text"]
    assert (
        f"http://localhost:3333/intelligence?proposal=review-proposal&decision={decision}" in reply
    )
    assert "Nothing was approved or executed" in reply
    assert db.execute(
        "SELECT decision_status FROM trade_proposals WHERE proposal_id='review-proposal'"
    ).fetchone() == ("PENDING",)
    assert db.execute(
        "SELECT count(*) FROM order_intents WHERE account_id=%s", (f"paper-ai:{owner}",)
    ).fetchone() == (0,)


@pytest.mark.parametrize(
    "command,own,expired,expected",
    [
        ("/approve review-proposal", False, False, "unavailable"),
        ("/approve review-proposal", True, True, "expired"),
        ("/reject review-proposal", True, True, "Review REJECT"),
        ("/approve review-proposal extra", True, False, "Use /approve"),
        ("/approve https://attacker.test", True, False, "Use /approve"),
    ],
)
def test_review_links_are_scoped_expiring_and_strictly_parsed(
    client, settings, db, command, own, expired, expected
):
    enroll(client, settings)
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    _insert_pending_proposal(
        db, owner, "review-proposal", age=timedelta(hours=2) if expired else timedelta(minutes=1)
    )
    encrypted = client.app.state.auth.crypto.encrypt("synthetic-bot-token")
    db.execute(
        "UPDATE telegram_config SET encrypted_bot_token=%s, chat_id=42, enabled=true, "
        "last_update_id=99 WHERE id=1",
        (encrypted,),
    )
    transport = FakeCommandTransport([_message(100, 42, command, "en")])
    client.portal.call(
        partial(
            run_telegram_command_tick,
            client.app.state.sessions,
            client.app.state.auth.crypto,
            transport,
            SequentialIds(),
            None,
            datetime.now(UTC),
            owner_id=owner if own else "other",
            web_origin="http://localhost:3333",
        )
    )
    assert expected in transport.sent[0][1]["text"]
    assert db.execute(
        "SELECT decision_status FROM trade_proposals WHERE proposal_id='review-proposal'"
    ).fetchone() == ("PENDING",)


def _decide_tick(client, owner, text):
    transport = FakeCommandTransport([_message(100, 42, text, "en")])
    client.portal.call(
        partial(
            run_telegram_command_tick,
            client.app.state.sessions,
            client.app.state.auth.crypto,
            transport,
            SequentialIds(),
            f"paper:{owner}",
            datetime.now(UTC),
            owner_id=owner,
            web_origin="http://localhost:3333",
            decide=partial(decide_from_telegram, client.app.state, owner),
        )
    )
    return transport.sent[0][1]["text"]


def _paired(client, settings, db):
    enroll(client, settings)
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    _insert_pending_proposal(db, owner, "review-proposal")
    encrypted = client.app.state.auth.crypto.encrypt("synthetic-bot-token")
    db.execute(
        "UPDATE telegram_config SET encrypted_bot_token=%s, chat_id=42, enabled=true, "
        "last_update_id=99 WHERE id=1",
        (encrypted,),
    )
    return owner


def _status(db):
    return db.execute(
        "SELECT decision_status FROM trade_proposals WHERE proposal_id='review-proposal'"
    ).fetchone()[0]


@pytest.mark.parametrize("decision,expected", [("approve", "APPROVED"), ("reject", "REJECTED")])
def test_telegram_decision_without_mfa_is_recorded_once(client, settings, db, decision, expected):
    owner = _paired(client, settings, db)
    reply = _decide_tick(client, owner, f"/{decision} review-proposal")
    assert expected in reply, reply
    assert _status(db) == expected
    # The same proposal cannot be decided twice.
    replay = _decide_tick(client, owner, "/reject review-proposal")
    assert "Not recorded" in replay and _status(db) == expected


def test_telegram_extra_arguments_change_nothing(client, settings, db):
    owner = _paired(client, settings, db)
    reply = _decide_tick(client, owner, "/approve review-proposal 000000")
    assert "Use /approve" in reply
    assert _status(db) == "PENDING"


def test_telegram_without_mfa_still_rejects_expired_proposal(client, settings, db):
    owner = _paired(client, settings, db)
    db.execute("UPDATE trade_proposals SET as_of = as_of - interval '2 hours'")
    reply = _decide_tick(client, owner, "/approve review-proposal")
    assert "Not recorded" in reply and "expired" in reply
    assert _status(db) == "PENDING"


def test_telegram_without_mfa_cannot_approve_another_owners_proposal(client, settings, db):
    owner = _paired(client, settings, db)
    # A deliberately unowned proposal cannot be claimed by the linked operator.
    db.execute("UPDATE trade_proposals SET owner_id = NULL")
    reply = _decide_tick(client, owner, "/approve review-proposal")
    assert "Not recorded" in reply and "not found" in reply
    assert _status(db) == "PENDING"
