import psycopg
import pyotp
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_breakers(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE breakers CASCADE")
    yield


def enroll(client, settings) -> None:
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


def seed_breaker(db, breaker_type: str, reason: str) -> None:
    db.execute(
        """INSERT INTO breakers (breaker_type, reason, tripped_at)
           VALUES (%s, %s, NOW())""",
        (breaker_type, reason),
    )


def test_list_breakers_requires_auth(client) -> None:
    assert client.get("/api/risk/breakers").status_code == 401


def test_list_breakers_is_empty_with_none_tripped(client, settings, db) -> None:
    enroll(client, settings)
    response = client.get("/api/risk/breakers")
    assert response.status_code == 200, response.text
    assert response.json() == {"rows": []}


def test_list_breakers_reports_an_active_breaker(client, settings, db) -> None:
    enroll(client, settings)
    seed_breaker(db, "DAILY_LOSS", "daily loss 0.03 at or beyond limit 0.02")

    response = client.get("/api/risk/breakers")

    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["breaker_type"] == "DAILY_LOSS"
    assert rows[0]["cleared_at"] is None


def test_clear_breaker_requires_auth(client) -> None:
    assert client.post("/api/risk/breakers/DAILY_LOSS/clear", json={}).status_code == 401


def test_clear_breaker_deactivates_an_active_breaker(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    seed_breaker(db, "DRAWDOWN", "drawdown 0.15 at or beyond limit 0.10")

    response = client.post(
        "/api/risk/breakers/DRAWDOWN/clear", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["breaker_type"] == "DRAWDOWN"
    assert body["cleared_at"] is not None
    assert body["cleared_by"] is not None

    listed = client.get("/api/risk/breakers").json()["rows"]
    assert listed[0]["cleared_at"] is not None


def test_clear_breaker_rejects_one_that_is_not_active(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/risk/breakers/WEEKLY_LOSS/clear", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 409


def test_clear_breaker_rejects_an_unknown_type(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/risk/breakers/NOT_A_REAL_BREAKER/clear", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 404
