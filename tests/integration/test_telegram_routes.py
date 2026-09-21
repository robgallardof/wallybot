from datetime import UTC, datetime, timedelta

import pyotp
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_telegram_config(db):
    # telegram_config is a singleton with no FK to `users`, so the shared `db` fixture's
    # TRUNCATE ... CASCADE (scoped to auth-adjacent tables) never touches it -- state would
    # otherwise leak across tests in file-declaration order.
    db.execute(
        "UPDATE telegram_config SET encrypted_bot_token = NULL, chat_id = NULL, "
        "enabled = false, pairing_code_hash = NULL WHERE id = 1"
    )
    db.execute("TRUNCATE telegram_confirmations CASCADE")
    yield


def enroll(client, settings) -> dict[str, object]:
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
    return finished.json()


def _insert_confirmation(
    db, confirmation_id: str, action: str, requested_at: datetime, expires_at: datetime
) -> None:
    db.execute(
        "INSERT INTO telegram_confirmations "
        "(confirmation_id, action, requested_at, expires_at) VALUES (%s, %s, %s, %s)",
        (confirmation_id, action, requested_at, expires_at),
    )


def test_telegram_routes_require_auth(client) -> None:
    assert client.get("/api/telegram").status_code == 401
    assert client.post("/api/telegram", json={}).status_code == 401


def test_default_telegram_config_has_no_bot_token(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/telegram")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "has_bot_token": False,
        "chat_id": None,
        "enabled": False,
        "pairing_status": "NEEDS_TOKEN",
        "pairing_code": None,
    }


def test_admin_can_set_bot_token_which_is_never_returned(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "has_bot_token": True,
        "chat_id": 42,
        "enabled": True,
        "pairing_status": "LINKED",
        "pairing_code": None,
    }
    assert "bot_token" not in body
    row = db.execute(
        "SELECT encrypted_bot_token FROM telegram_config WHERE id = 1"
    ).fetchone()
    assert row[0] not in (None, "123456:my-secret-token")


def test_updating_chat_id_without_a_new_token_keeps_the_existing_one(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 1, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    response = client.post(
        "/api/telegram",
        json={"chat_id": 2, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "has_bot_token": True,
        "chat_id": 2,
        "enabled": True,
        "pairing_status": "LINKED",
        "pairing_code": None,
    }


def test_token_only_setup_returns_one_time_pairing_code(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pairing_status"] == "WAITING_FOR_START"
    assert body["pairing_code"]
    assert body["chat_id"] is None
    assert client.get("/api/telegram").json()["pairing_code"] is None
    stored = db.execute("SELECT pairing_code_hash FROM telegram_config WHERE id = 1").fetchone()[0]
    assert stored is not None and stored != body["pairing_code"]


def test_viewer_can_read_but_cannot_change_telegram_config(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role = 'VIEWER'")

    assert client.get("/api/telegram").status_code == 200
    response = client.post(
        "/api/telegram",
        json={"bot_token": "x", "chat_id": 1, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 403


class FakeTelegramTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        self.calls.append((url, form))


def test_system_reports_telegram_enabled_only_once_fully_configured(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    assert client.get("/api/system").json()["telegram"] == "DISABLED"

    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert client.get("/api/system").json()["telegram"] == "ENABLED"


def test_pausing_the_bot_sends_a_telegram_notification_when_configured(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport

    response = client.post(
        "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert len(transport.calls) == 1
    url, form = transport.calls[0]
    assert url == "https://api.telegram.org/bot123456:my-secret-token/sendMessage"
    assert form["chat_id"] == "42"
    assert "[WARNING] Bot paused" in form["text"]


def test_control_change_sends_nothing_when_telegram_is_not_configured(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport

    response = client.post(
        "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert transport.calls == []


def test_repeating_the_same_status_sends_no_notification(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport

    client.post("/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf})
    transport.calls.clear()
    response = client.post(
        "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert transport.calls == []


def test_a_repeated_status_change_within_the_dedup_window_sends_no_second_notification(
    client, settings
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport

    client.post("/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf})
    client.post("/api/control", json={"status": "RUNNING"}, headers={"X-CSRF-Token": csrf})
    response = client.post(
        "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    # Three real state changes happened (paused, resumed, paused again), but the second "Bot
    # paused" repeats the exact same severity+title as the first within the 5-minute dedup
    # window, so only two of the three notifications actually reach the transport.
    assert len(transport.calls) == 2
    assert "Bot paused" in transport.calls[0][1]["text"]
    assert "Bot resumed" in transport.calls[1][1]["text"]


def test_confirmations_route_requires_auth(client) -> None:
    assert client.get("/api/telegram/confirmations").status_code == 401


def test_pending_confirmations_are_listed(client, settings, db) -> None:
    enroll(client, settings)
    now = datetime.now(UTC)
    _insert_confirmation(db, "conf1", "PAUSE", now, now + timedelta(minutes=5))

    response = client.get("/api/telegram/confirmations")

    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["confirmation_id"] == "conf1"
    assert rows[0]["action"] == "PAUSE"
    assert rows[0]["confirmed_at"] is None


def test_expired_confirmations_are_not_listed_as_pending(client, settings, db) -> None:
    enroll(client, settings)
    now = datetime.now(UTC)
    _insert_confirmation(
        db, "conf1", "PAUSE", now - timedelta(minutes=10), now - timedelta(minutes=5)
    )

    response = client.get("/api/telegram/confirmations")

    assert response.status_code == 200, response.text
    assert response.json()["rows"] == []


def test_confirming_a_pause_request_pauses_the_bot_and_requires_admin(
    client, settings, db
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    now = datetime.now(UTC)
    _insert_confirmation(db, "conf1", "PAUSE", now, now + timedelta(minutes=5))

    response = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["confirmed_at"] is not None
    assert body["confirmed_by"]

    dashboard = client.get("/api/dashboard")
    assert dashboard.json()["status"] == "PAUSED"


def test_confirming_notifies_over_telegram_when_the_status_actually_changes(
    client, settings, db
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport
    now = datetime.now(UTC)
    _insert_confirmation(db, "conf1", "PAUSE", now, now + timedelta(minutes=5))

    response = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert len(transport.calls) == 1
    assert "Confirmado desde la web" in transport.calls[0][1]["text"]


def test_confirming_a_resume_that_is_already_the_current_status_sends_no_notification(
    client, settings, db
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/telegram",
        json={"bot_token": "123456:my-secret-token", "chat_id": 42, "enabled": True},
        headers={"X-CSRF-Token": csrf},
    )
    transport = FakeTelegramTransport()
    client.app.state.telegram_transport = transport
    now = datetime.now(UTC)
    # Default control status is RUNNING -- confirming a RESUME is a no-op state change.
    _insert_confirmation(db, "conf1", "RESUME", now, now + timedelta(minutes=5))

    response = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert transport.calls == []


def test_confirming_an_unknown_confirmation_is_a_404(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/telegram/confirmations/does-not-exist/confirm",
        json={},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 404


def test_confirming_an_expired_confirmation_is_rejected(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    now = datetime.now(UTC)
    _insert_confirmation(
        db, "conf1", "PAUSE", now - timedelta(minutes=10), now - timedelta(minutes=5)
    )

    response = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 409


def test_confirming_twice_only_succeeds_once(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    now = datetime.now(UTC)
    _insert_confirmation(db, "conf1", "PAUSE", now, now + timedelta(minutes=5))

    first = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )
    second = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 409


def test_viewer_cannot_confirm_a_telegram_confirmation(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role = 'VIEWER'")
    now = datetime.now(UTC)
    _insert_confirmation(db, "conf1", "PAUSE", now, now + timedelta(minutes=5))

    response = client.post(
        "/api/telegram/confirmations/conf1/confirm", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 403
