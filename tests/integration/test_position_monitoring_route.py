from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest

from tests.integration.test_portfolio_route import add_executed_proposal, add_fill_for, enroll
from wallybot.domain.market import MarketSnapshot

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("age,available", [(0, True), (61, False), (-60, False)])
def test_history_marks_only_fresh_quotes_and_keeps_confirmed_cost(
    client, settings, db, age, available
):
    enroll(client, settings)
    owner_id = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    order_id = f"marked-{owner_id}"
    add_fill_for(db, f"paper-ai:{owner_id}", f"fill-{owner_id}", order_id)
    add_executed_proposal(db, owner_id, "marked-proposal", order_id)
    db.execute(
        "UPDATE trade_proposals SET stop_price=48000, take_profit_price=54000 "
        "WHERE proposal_id='marked-proposal'"
    )

    class Provider:
        async def fetch_snapshot(self, instrument):
            return MarketSnapshot(
                instrument,
                Decimal("55000"),
                Decimal("55001"),
                datetime.now(UTC) - timedelta(seconds=age),
                "kraken",
            )

    client.app.state.portfolio_market_provider = Provider()
    response = client.get("/api/portfolio/ai")
    assert response.status_code == 200
    item = response.json()["proposal_history"][0]
    assert item["remaining_quantity"] == "0.005"
    assert item["realized_pnl"] == "0"
    assert item["current_price"] == ("55000" if available else None)
    assert item["unrealized_pnl"] == ("24.750" if available else None)
    assert item["monitoring_status"] == ("TARGET_REACHED" if available else "QUOTE_UNAVAILABLE")
    assert client.get("/api/portfolio").json()["proposal_history"] == []


def test_native_analyst_can_only_announce_its_own_heartbeat_not_write_orders(settings, db):
    db.execute("SET ROLE wally_ai")
    try:
        db.execute("SELECT public.record_ai_worker_heartbeat(100)")
        for table in ("order_intents", "fills", "ledger_accounts", "ledger_postings"):
            row = db.execute(
                "SELECT has_table_privilege(current_user, %s, 'INSERT')", (table,)
            ).fetchone()
            assert row == (False,)
            row = db.execute(
                "SELECT has_table_privilege(current_user, %s, 'SELECT')", (table,)
            ).fetchone()
            assert row == (False,)
        assert db.execute(
            "SELECT has_table_privilege(current_user, 'trade_proposals', 'INSERT')"
        ).fetchone() == (True,)
        assert db.execute(
            "SELECT has_table_privilege(current_user, 'heartbeats', 'UPDATE')"
        ).fetchone() == (False,)
    finally:
        db.execute("RESET ROLE")
    assert db.execute(
        "SELECT service, timestamp FROM heartbeats WHERE service='ai_worker'"
    ).fetchone() == ("ai_worker", 100)


def test_native_analyst_reports_cli_availability_only_through_bounded_function(settings, db):
    db.execute("SET ROLE wally_ai")
    try:
        db.execute("SELECT public.record_ai_analyst_status('claude', false, 200)")
        assert db.execute(
            "SELECT has_table_privilege(current_user, 'ai_analyst_status', 'UPDATE')"
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("SELECT public.record_ai_analyst_status('gpt', true, 200)")
    finally:
        db.execute("RESET ROLE")
    assert db.execute(
        "SELECT analyst, available, checked_at FROM ai_analyst_status"
    ).fetchone() == ("claude", False, 200)
