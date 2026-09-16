from uuid import uuid4

import pyotp
import pytest

pytestmark = pytest.mark.integration


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


def create_connection(client, csrf: str, **overrides) -> dict[str, object]:
    body = {
        "provider": "KRAKEN",
        "label": "Cuenta principal",
        "mode": "READ_ONLY",
    }
    body.update(overrides)
    response = client.post("/api/connections", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    return response.json()


def test_connection_routes_require_auth(client) -> None:
    assert client.get("/api/connections").status_code == 401
    assert client.post("/api/connections", json={}).status_code == 401


def test_admin_can_create_and_list_its_connection(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    created = create_connection(client, csrf)

    assert created["provider"] == "KRAKEN"
    assert created["label"] == "Cuenta principal"
    assert created["mode"] == "READ_ONLY"
    assert created["status"] == "PENDING"
    assert isinstance(created["created_at"], int)

    listed = client.get("/api/connections")
    assert listed.status_code == 200, listed.text
    assert listed.json() == {"rows": [created]}


def test_creating_connection_requires_csrf(client, settings, db) -> None:
    enroll(client, settings)

    response = client.post(
        "/api/connections",
        json={"provider": "BINANCE", "label": "Sin CSRF", "mode": "READ_ONLY"},
    )

    assert response.status_code == 403
    assert db.execute("SELECT count(*) FROM provider_connections").fetchone()[0] == 0


def test_viewer_can_read_but_cannot_create_connections(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role = 'VIEWER'")

    assert client.get("/api/connections").status_code == 200
    response = client.post(
        "/api/connections",
        json={"provider": "COINBASE", "label": "Solo lectura", "mode": "READ_ONLY"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 403
    assert db.execute("SELECT count(*) FROM provider_connections").fetchone()[0] == 0


def test_credentials_are_encrypted_and_never_returned(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    created = create_connection(
        client, csrf, provider="BINANCE", api_key="my-api-key", api_secret="my-api-secret"
    )

    assert created["has_credentials"] is True
    assert "api_key" not in created
    assert "api_secret" not in created
    assert "encrypted_key" not in created
    assert "encrypted_secret" not in created
    row = db.execute(
        "SELECT encrypted_key, encrypted_secret FROM provider_connections WHERE id = %s",
        (created["id"],),
    ).fetchone()
    assert row[0] not in (None, "my-api-key")
    assert row[1] not in (None, "my-api-secret")

    listed = client.get("/api/connections").json()["rows"]
    assert listed == [created]


def test_a_connection_with_no_credentials_reports_has_credentials_false(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    created = create_connection(client, csrf)

    assert created["has_credentials"] is False


def test_connections_are_scoped_to_the_signed_in_user(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    own = create_connection(client, csrf, label="Cuenta compartida")
    other_user_id = str(uuid4())
    db.execute(
        """
        INSERT INTO users
            (id, username, password_hash, totp_encrypted, last_totp_step, role, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (other_user_id, "another-user", "not-a-secret", "not-a-secret", -1, "ADMIN", 0),
    )
    db.execute(
        """
        INSERT INTO provider_connections (id, user_id, provider, label, mode, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (str(uuid4()), other_user_id, "KRAKEN", "Cuenta compartida", "PAPER", "HEALTHY", 0),
    )

    response = client.get("/api/connections")

    assert response.status_code == 200, response.text
    assert response.json() == {"rows": [own]}
