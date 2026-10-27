from concurrent.futures import ThreadPoolExecutor

import pyotp
import pytest

from wallybot.security.crypto import digest

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
    assert client.get("/api/dashboard").json()["environment"] == "OBSERVE"
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


def test_confirm_mfa_refreshes_a_stale_admin_session_without_a_new_login(client, settings, db):
    enrollment, _ = enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    # Simulate a session older than admin()'s 5-minute recent-MFA window (apps/api/dependencies.py).
    db.execute("UPDATE sessions SET mfa_at = mfa_at - 301")

    stale = client.post("/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf})
    assert stale.status_code == 403
    assert stale.json()["detail"] == "Sign in again with MFA to confirm this action"

    db.execute("UPDATE users SET last_totp_step=-1")
    code = pyotp.TOTP(enrollment["secret"]).now()
    confirmed = client.post(
        "/api/auth/confirm-mfa", json={"code": code}, headers={"X-CSRF-Token": csrf}
    )
    assert confirmed.status_code == 200, confirmed.text

    # Same cookie/CSRF as before -- confirm-mfa refreshes the existing session, it doesn't rotate.
    retried = client.post("/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf})
    assert retried.status_code == 200, retried.text
    assert db.execute("SELECT status FROM control").fetchone()[0] == "PAUSED"


def test_confirm_mfa_rejects_a_wrong_code_without_refreshing_the_session(client, settings, db):
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE sessions SET mfa_at = mfa_at - 301")

    rejected = client.post(
        "/api/auth/confirm-mfa", json={"code": "000000"}, headers={"X-CSRF-Token": csrf}
    )
    assert rejected.status_code == 401

    still_stale = client.post(
        "/api/control", json={"status": "PAUSED"}, headers={"X-CSRF-Token": csrf}
    )
    assert still_stale.status_code == 403


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


PASSWORD = "correct-horse-battery-staple"


def login_again(client, settings, db, secret: str) -> str:
    """Logs in a second time on the same TestClient, overwriting its stored session cookie with
    a brand-new session -- the previous session row still exists server-side untouched. Returns
    the new raw session cookie."""
    db.execute("UPDATE users SET last_totp_step=-1")
    challenge = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["challenge"]
    response = client.post(
        "/api/auth/mfa", json={"challenge": challenge, "code": pyotp.TOTP(secret).now()}
    )
    assert response.status_code == 200, response.text
    return client.cookies[settings.cookie_name]


def test_password_change_requires_auth(client) -> None:
    response = client.post(
        "/api/auth/password", json={"current_password": "x", "new_password": "y" * 12}
    )
    assert response.status_code == 401


def test_password_change_requires_fresh_mfa(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE sessions SET mfa_at = mfa_at - 301")

    response = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "a-new-long-password"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Sign in again with MFA to confirm this action"


def test_password_change_rejects_a_wrong_current_password(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/auth/password",
        json={"current_password": "not-the-real-password", "new_password": "a-new-long-password"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 401


def test_password_change_updates_login_and_revokes_only_other_sessions(
    client, settings, db
) -> None:
    enrollment, _ = enroll(client, settings)
    session_a = client.cookies[settings.cookie_name]
    session_b = login_again(client, settings, db, enrollment["secret"])
    assert session_a != session_b
    csrf = client.get("/api/auth/me").json()["csrf"]

    changed = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "a-new-long-password"},
        headers={"X-CSRF-Token": csrf},
    )
    assert changed.status_code == 200, changed.text

    # The old password no longer authenticates.
    old_login = client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    assert old_login.status_code == 401

    # The new password does.
    new_login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "a-new-long-password"}
    )
    assert new_login.status_code == 200

    # Session A (not the one that made the change) was revoked...
    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_a}).status_code == 401
    # ...session B (the one that made the change) was not.
    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_b}).status_code == 200


def test_totp_replace_requires_fresh_mfa(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE sessions SET mfa_at = mfa_at - 301")

    response = client.post("/api/auth/totp/replace/start", json={}, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 403


def test_totp_replace_finish_rejects_a_wrong_code(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    start = client.post("/api/auth/totp/replace/start", json={}, headers={"X-CSRF-Token": csrf})
    assert start.status_code == 200, start.text

    response = client.post(
        "/api/auth/totp/replace/finish",
        json={"challenge": start.json()["challenge"], "code": "000000"},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 401


def test_totp_replace_happy_path_switches_the_active_secret(client, settings, db) -> None:
    enrollment, _ = enroll(client, settings)
    session_a = client.cookies[settings.cookie_name]
    session_b = login_again(client, settings, db, enrollment["secret"])
    csrf = client.get("/api/auth/me").json()["csrf"]

    start = client.post("/api/auth/totp/replace/start", json={}, headers={"X-CSRF-Token": csrf})
    assert start.status_code == 200, start.text
    new_secret = start.json()["secret"]

    finish = client.post(
        "/api/auth/totp/replace/finish",
        json={"challenge": start.json()["challenge"], "code": pyotp.TOTP(new_secret).now()},
        headers={"X-CSRF-Token": csrf},
    )
    assert finish.status_code == 200, finish.text

    # The old secret no longer authenticates a login.
    old_challenge = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["challenge"]
    old_mfa = client.post(
        "/api/auth/mfa",
        json={"challenge": old_challenge, "code": pyotp.TOTP(enrollment["secret"]).now()},
    )
    assert old_mfa.status_code == 401

    # The new secret does.
    db.execute("UPDATE users SET last_totp_step=-1")
    new_challenge = client.post(
        "/api/auth/login", json={"username": "admin", "password": PASSWORD}
    ).json()["challenge"]
    new_mfa = client.post(
        "/api/auth/mfa",
        json={"challenge": new_challenge, "code": pyotp.TOTP(new_secret).now()},
    )
    assert new_mfa.status_code == 200

    # Session A (not the one that made the change) was revoked; session B was not.
    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_a}).status_code == 401
    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_b}).status_code == 200


def test_sessions_requires_auth(client) -> None:
    assert client.get("/api/auth/sessions").status_code == 401


def test_sessions_lists_every_session_and_marks_the_current_one(client, settings, db) -> None:
    enrollment, _ = enroll(client, settings)
    session_a = client.cookies[settings.cookie_name]
    session_b = login_again(client, settings, db, enrollment["secret"])

    rows = client.get("/api/auth/sessions").json()["rows"]

    assert len(rows) == 2
    ids = {row["session_id"] for row in rows}
    assert ids == {digest(session_a), digest(session_b)}
    current = [row for row in rows if row["is_current"]]
    assert len(current) == 1
    assert current[0]["session_id"] == digest(session_b)


def test_revoke_session_requires_auth(client) -> None:
    assert client.request("DELETE", "/api/auth/sessions/not-a-real-id", json={}).status_code == 401


def test_revoke_session_rejects_an_unknown_session(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.request(
        "DELETE", "/api/auth/sessions/not-a-real-id", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 404


def test_revoke_session_removes_the_target_and_leaves_the_caller_signed_in(
    client, settings, db
) -> None:
    enrollment, _ = enroll(client, settings)
    session_a = client.cookies[settings.cookie_name]
    session_b = login_again(client, settings, db, enrollment["secret"])
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.request(
        "DELETE", f"/api/auth/sessions/{digest(session_a)}", json={}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200, response.text

    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_a}).status_code == 401
    assert client.get("/api/auth/me", cookies={settings.cookie_name: session_b}).status_code == 200
