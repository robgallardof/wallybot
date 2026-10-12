from datetime import UTC, datetime, timedelta
from functools import partial

import pytest

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
