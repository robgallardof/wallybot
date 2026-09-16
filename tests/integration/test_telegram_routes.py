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
        "enabled = false WHERE id = 1"
    )
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


def test_telegram_routes_require_auth(client) -> None:
    assert client.get("/api/telegram").status_code == 401
    assert client.post("/api/telegram", json={}).status_code == 401


def test_default_telegram_config_has_no_bot_token(client, settings) -> None:
    enroll(client, settings)

    response = client.get("/api/telegram")

    assert response.status_code == 200, response.text
    assert response.json() == {"has_bot_token": False, "chat_id": None, "enabled": False}


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
    assert body == {"has_bot_token": True, "chat_id": 42, "enabled": True}
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
    assert response.json() == {"has_bot_token": True, "chat_id": 2, "enabled": True}


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
