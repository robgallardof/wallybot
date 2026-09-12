from concurrent.futures import ThreadPoolExecutor

import pyotp
import pytest

pytestmark = pytest.mark.integration


def enroll(client, settings):
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    result = client.post("/api/auth/setup/start", json=body)
    assert result.status_code == 200, result.text
    enrollment = result.json()
    finish = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finish.status_code == 200, finish.text
    return enrollment, finish.json()


def test_setup_login_recovery_logout_and_persistence(client, settings, db):
    assert client.get("/health/ready").status_code == 200
    assert client.get("/api/dashboard").status_code == 401
    enrollment, result = enroll(client, settings)
    assert not client.get("/api/auth/setup-status").json()["setup_required"]
    assert client.get("/api/dashboard").json()["environment"] == "PAPER"
    assert client.post("/api/control", json={"status": "PAUSED"}).status_code == 403
    csrf = client.get("/api/auth/me").json()["csrf"]
    assert (
        client.post(
            "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 200
    )
    assert db.execute("SELECT status FROM control").fetchone()[0] == "PAUSED"
    assert (
        client.post(
            "/api/control", json={"status": "LIVE"}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/auth/logout", json={}, headers={"X-CSRF-Token": csrf}).status_code == 200
    )
    assert client.get("/api/dashboard").status_code == 401
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "correct-horse-battery-staple"}
    ).json()
    # The enrollment TOTP was consumed; use a one-time recovery code for immediate login.
    response = client.post(
        "/api/auth/mfa", json={"challenge": login["challenge"], "code": result["recovery_codes"][0]}
    )
    assert response.status_code == 200
    assert client.get("/api/dashboard").json()["status"] == "PAUSED"
    assert db.execute("SELECT count(*) FROM recovery_codes").fetchone()[0] == 7
    assert (
        client.post(
            "/api/auth/mfa",
            json={"challenge": login["challenge"], "code": result["recovery_codes"][0]},
        ).status_code
        == 401
    )
    stored = db.execute("SELECT password_hash, totp_encrypted FROM users").fetchone()
    assert stored[0].startswith("$argon2id$")
    assert enrollment["secret"] not in stored[1]


def test_setup_race_creates_one_admin(client, settings, db):
    first = client.post(
        "/api/auth/setup/start",
        json={
            "username": "admin",
            "password": "long-test-password",
            "bootstrap_token": settings.bootstrap_token.get_secret_value(),
        },
    ).json()
    payload = {
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
        "challenge": first["challenge"],
        "code": pyotp.TOTP(first["secret"]).now(),
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post("/api/auth/setup/finish", json=payload).status_code, range(2)
            )
        )
    assert sorted(responses) == [200, 409]
    assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 1


def test_viewer_and_expired_sessions(client, settings, db):
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role='VIEWER'")
    assert client.get("/api/dashboard").status_code == 200
    assert (
        client.post(
            "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 403
    )
    db.execute("UPDATE sessions SET expires_at=0")
    assert client.get("/api/auth/me").status_code == 401


def test_origin_validation_redaction_and_invalid_bootstrap(client):
    assert (
        client.post(
            "/api/auth/login", json={}, headers={"Origin": "https://evil.invalid"}
        ).status_code
        == 403
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret-value", "extra": "secret-value"},
    )
    assert response.status_code == 422
    assert "secret-value" not in response.text
    assert (
        client.post(
            "/api/auth/setup/start",
            json={
                "username": "admin",
                "password": "long-test-password",
                "bootstrap_token": "x" * 32,
            },
        ).status_code
        == 401
    )


def test_totp_concurrency_and_replay(client, settings, db):
    enrollment, _ = enroll(client, settings)
    db.execute("UPDATE users SET last_totp_step=-1")
    challenges = [
        client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "correct-horse-battery-staple"},
        ).json()["challenge"]
        for _ in range(2)
    ]
    code = pyotp.TOTP(enrollment["secret"]).now()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda challenge: (
                    client.post(
                        "/api/auth/mfa", json={"challenge": challenge, "code": code}
                    ).status_code
                ),
                challenges,
            )
        )
    assert sorted(responses) == [200, 401]


def test_shared_throttle_fails_closed(settings, db):
    from fastapi.testclient import TestClient

    from apps.api.main import create_app
    from wallybot.infrastructure.loop import selector_loop

    strict = settings.model_copy(update={"auth_limit": 1})
    with TestClient(
        create_app(strict),
        base_url=settings.origin,
        headers={"Origin": settings.origin},
        backend_options={"loop_factory": selector_loop},
    ) as c:
        # Existing counters from other tests can only strengthen this assertion.
        c.post("/api/auth/login", json={"username": "absent", "password": "x"})
        assert (
            c.post("/api/auth/login", json={"username": "absent", "password": "x"}).status_code
            == 429
        )
