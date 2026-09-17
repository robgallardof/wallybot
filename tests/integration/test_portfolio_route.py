from decimal import Decimal
from uuid import uuid4

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


def add_balanced_posting_pair(
    db, account_id: str, currency: str, purpose: str, amount: str, reference: str
) -> None:
    value = Decimal(amount)
    own_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES (%s, %s, %s) RETURNING id""",
        (account_id, currency, purpose),
    ).fetchone()[0]
    clearing_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES ('clearing', %s, 'CLEARING')
           ON CONFLICT (account_id, currency, purpose) DO UPDATE SET currency = EXCLUDED.currency
           RETURNING id""",
        (currency,),
    ).fetchone()[0]
    transaction_id = str(uuid4())
    db.execute(
        """INSERT INTO ledger_transactions
           (transaction_id, account_id, reason, reference_id, recorded_at)
           VALUES (%s, %s, 'FILL', %s, NOW())""",
        (transaction_id, account_id, reference),
    )
    db.execute(
        """INSERT INTO ledger_postings (transaction_id, ledger_account_id, amount)
           VALUES (%s, %s, %s), (%s, %s, %s)""",
        (transaction_id, own_account, value, transaction_id, clearing_account, -value),
    )


def add_fill(db, account_id: str) -> None:
    db.execute(
        """INSERT INTO order_intents (
             client_order_id, account_id, environment, venue, base, quote, side, kind, quantity,
             limit_price, decision_id, idempotency_key, risk_assessment_id, config_versions,
             created_at, expires_at, status
           ) VALUES (
             'portfolio-order', %s, 'PAPER', 'kraken', 'BTC', 'USD', 'BUY', 'MARKET', 0.005,
             NULL, 'decision-1', 'portfolio-key', 'risk-1', '{}'::jsonb,
             NOW(), NOW() + interval '1 hour', 'FILLED'
           )""",
        (account_id,),
    )
    db.execute(
        """INSERT INTO fills (
             fill_id, client_order_id, account_id, environment, venue, base, quote, side,
             quantity, price, fee, fee_currency, filled_at
           ) VALUES (
             'portfolio-fill', 'portfolio-order', %s, 'PAPER', 'kraken', 'BTC', 'USD', 'BUY',
             0.005, 50000, 0.25, 'USD', NOW()
           )""",
        (account_id,),
    )


def test_portfolio_requires_auth(client) -> None:
    assert client.get("/api/portfolio").status_code == 401


def test_portfolio_reads_only_the_signed_in_users_paper_ledger(client, settings, db) -> None:
    enroll(client, settings)
    user_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    own_account_id = f"paper:{user_id}"

    add_balanced_posting_pair(db, own_account_id, "USD", "CASH", "-250.25", "cash-fill")
    add_balanced_posting_pair(db, own_account_id, "BTC", "POSITION", "0.005", "btc-fill")
    add_fill(db, own_account_id)
    add_balanced_posting_pair(db, "paper:another-user", "USD", "CASH", "99999", "other-fill")

    response = client.get("/api/portfolio")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["environment"] == "PAPER"
    assert body["connection_count"] == 0
    assert body["balances"] == [
        {"currency": "USD", "purpose": "CASH", "amount": "-250.25"},
        {"currency": "BTC", "purpose": "POSITION", "amount": "0.005"},
    ]
    assert body["activity"] == [
        {
            "id": "portfolio-fill",
            "venue": "kraken",
            "base": "BTC",
            "quote": "USD",
            "side": "BUY",
            "quantity": "0.005",
            "price": "50000",
            "fee": "0.25",
            "fee_currency": "USD",
            "occurred_at": body["activity"][0]["occurred_at"],
        }
    ]
