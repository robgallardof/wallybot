"""GET/POST /api/portfolio/ai -- the AI-autonomous account's own view/funding, fully separate
from GET/POST /api/portfolio (docs/adr/016-ai-autonomous-account.md, 2026-09-23).
"""

import pyotp
import pytest

pytestmark = pytest.mark.integration


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


def test_ai_portfolio_requires_auth(client) -> None:
    assert client.get("/api/portfolio/ai").status_code == 401
    assert client.post("/api/portfolio/ai/fund", json={"amount": "1000"}).status_code == 401


def test_ai_fund_credits_the_ai_account_only(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    funded = client.post(
        "/api/portfolio/ai/fund", json={"amount": "5000"}, headers={"X-CSRF-Token": csrf}
    )
    assert funded.status_code == 201
    balances = funded.json()["balances"]
    assert any(b["currency"] == "USD" and b["amount"] == "5000" for b in balances)

    ai_view = client.get("/api/portfolio/ai").json()
    assert any(b["amount"] == "5000" for b in ai_view["balances"])

    # The deterministic account is untouched by funding the AI one.
    main_view = client.get("/api/portfolio").json()
    assert main_view["balances"] == []


def test_ai_fund_rejects_a_second_attempt(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    headers = {"X-CSRF-Token": csrf}

    first = client.post("/api/portfolio/ai/fund", json={"amount": "5000"}, headers=headers)
    assert first.status_code == 201
    second = client.post("/api/portfolio/ai/fund", json={"amount": "1000"}, headers=headers)
    assert second.status_code == 409


def test_funding_the_main_account_does_not_fund_the_ai_account(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    client.post("/api/portfolio/fund", json={"amount": "10000"}, headers={"X-CSRF-Token": csrf})

    ai_view = client.get("/api/portfolio/ai").json()
    assert ai_view["balances"] == []
