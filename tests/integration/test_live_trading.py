"""Real mode with scripted private HTTP semantics and real PostgreSQL. Never funded keys."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.integration.test_connection_routes import enroll
from tests.integration.test_proposal_execution import ControlledProvider, _row
from wallybot.domain.market import Instrument, MarketType
from wallybot.exchanges.kraken_private import REQUIRED_PERMISSIONS, KrakenPrivateError

pytestmark = pytest.mark.integration

INSTRUMENT = Instrument(
    "kraken",
    MarketType.SPOT,
    "XBT",
    "USD",
    Decimal("0.1"),
    Decimal("0.00000001"),
    Decimal("0.00001"),
)


class PublicTransport:
    async def get(self, path, params):
        if path.endswith("AssetPairs"):
            return {"result": {"XXBTZUSD": {"costmin": "5"}}}
        if path.endswith("Depth"):
            now = str(datetime.now(UTC).timestamp())
            return {
                "result": {
                    "XXBTZUSD": {"asks": [["51905", "10", now]], "bids": [["51895", "10", now]]}
                }
            }
        raise AssertionError(path)


class Provider(ControlledProvider):
    def __init__(self):
        super().__init__(datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
        self.snapshot = replace(self.snapshot, instrument=INSTRUMENT, source="kraken")
        self.snapshot = replace(self.snapshot, timestamp=datetime.now(UTC))
        self.candles = [replace(c, instrument=INSTRUMENT, source="kraken") for c in self.candles]
        self.transport = PublicTransport()

    async def discover_instruments(self):
        return [INSTRUMENT]


class Private:
    def __init__(self):
        self.balances = {"ZUSD": Decimal("1000")}
        self.orders = {}
        self.trades = {}
        self.calls = []
        self.forbidden = False
        self.timeout = False
        self.external_open = False

    async def call(self, method, params):
        self.calls.append((method, params.copy()))
        if method == "GetApiKeyInfo":
            return {
                "permissions": sorted(
                    REQUIRED_PERMISSIONS | ({"withdraw-funds"} if self.forbidden else set())
                )
            }
        if method == "BalanceEx":
            return {
                asset: {"balance": str(total), "hold_trade": "0"}
                for asset, total in self.balances.items()
            }
        if method == "OpenOrders":
            return {"open": {"external": {}} if self.external_open else {}}
        if method == "ClosedOrders":
            return {"closed": self.orders.copy(), "count": len(self.orders)}
        if method == "QueryTrades":
            return {key: self.trades[key] for key in params["txid"].split(",")}
        if method == "TradeVolume":
            return {"fees": {"XXBTZUSD": {"fee": "0.1"}}}
        if method == "AddOrder":
            volume, price = Decimal(params["volume"]), Decimal(params["price"])
            cost, fee = volume * price, volume * price * Decimal("0.001")
            venue_id = "venue-" + str(len(self.orders) + 1)
            trade_id = "trade-" + str(len(self.orders) + 1)
            self.orders[venue_id] = {
                "cl_ord_id": params["cl_ord_id"],
                "descr": {"pair": "XBTUSD", "type": params["type"]},
                "vol": str(volume),
                "vol_exec": str(volume),
                "price": str(price),
                "status": "closed",
                "trades": [trade_id],
            }
            self.trades[trade_id] = {
                "ordertxid": venue_id,
                "type": params["type"],
                "vol": str(volume),
                "price": str(price),
                "cost": str(cost),
                "fee": str(fee),
                "time": str(datetime.now(UTC).timestamp()),
                "margin": "0",
            }
            if params["type"] == "buy":
                self.balances["ZUSD"] -= cost + fee
                self.balances["XXBT"] = self.balances.get("XXBT", Decimal(0)) + volume
            else:
                self.balances["ZUSD"] += cost - fee
                self.balances["XXBT"] -= volume
            if self.timeout:
                raise KrakenPrivateError("accepted but response lost")
            return {"txid": [venue_id]}
        raise AssertionError(method)


@pytest.fixture
def setup_live(client, settings, db, monkeypatch):
    monkeypatch.setattr(client.app.state.settings, "live_capable", True)
    db.execute("UPDATE control SET environment='OBSERVE'")
    db.execute(
        "UPDATE ai_autonomy_control SET target_core_pct=0.70, target_growth_pct=0.20, "
        "target_speculative_pct=0.10"
    )
    db.execute(
        "TRUNCATE equity_snapshots, breakers, ledger_postings, ledger_transactions, "
        "ledger_accounts, fills, order_transitions, order_intents, shadow_decisions, "
        "trade_proposals CASCADE"
    )
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    private = Private()

    def factory(key, secret):
        return private

    client.app.state.kraken_private_factory = factory
    service = client.app.state.live_trading
    service.transport_factory = factory
    service.provider = Provider()
    connection = client.post(
        "/api/connections",
        headers={"X-CSRF-Token": csrf},
        json={
            "provider": "KRAKEN",
            "label": "Real account",
            "mode": "TRADE_ONLY",
            "api_key": "fake-key",
            "api_secret": "fake-secret",
        },
    )
    assert connection.status_code == 200
    body = {
        "connection_id": connection.json()["id"],
        "enabled": True,
        "confirmation": "LIVE",
        "max_order_usd": "100",
        "max_daily_loss_usd": "10",
        "max_total_usd": "200",
        "slippage_pct": "0.005",
    }
    return client, db, csrf, owner, private, service, body


def activate(setup):
    client, _, csrf, _, _, _, body = setup
    response = client.post("/api/live/control", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    return response.json()


def proposal(setup, direction="LONG"):
    client, _, _, owner, _, service, _ = setup
    row = _row(direction=direction, as_of=datetime.now(UTC) - timedelta(minutes=1))
    row.proposal_id = str(uuid4())
    row.venue, row.base = "kraken", "XBT"
    row.owner_id, row.decision_status = owner, "PENDING"

    from psycopg.types.json import Jsonb

    setup[1].execute(
        """INSERT INTO trade_proposals
        (proposal_id, venue, base, quote, direction, strategy_id, confidence,
         suggested_allocation_pct, entry_price, time_horizon_seconds, signal_ttl_seconds,
         reasons, risks, supporting_signal_ids, invalidating_conditions, source_event_ids,
         model_id, prompt_version, as_of, owner_id, decision_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            row.proposal_id,
            row.venue,
            row.base,
            row.quote,
            row.direction,
            row.strategy_id,
            row.confidence,
            row.suggested_allocation_pct,
            row.entry_price,
            row.time_horizon_seconds,
            row.signal_ttl_seconds,
            Jsonb(row.reasons),
            Jsonb(row.risks),
            Jsonb([]),
            Jsonb([]),
            Jsonb([]),
            row.model_id,
            row.prompt_version,
            row.as_of,
            row.owner_id,
            row.decision_status,
        ),
    )
    return row.proposal_id


def approve(setup, proposal_id, version):
    client, _, csrf, _, _, _, _ = setup
    return client.post(
        f"/api/proposals/{proposal_id}/approve",
        json={"environment": "LIVE", "live_version": version},
        headers={"X-CSRF-Token": csrf},
    )


def test_activation_requires_explicit_confirmation_and_preserves_default(setup_live):
    client, db, csrf, _, private, _, body = setup_live
    body.pop("confirmation")
    response = client.post("/api/live/control", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert db.execute("SELECT environment FROM control").fetchone()[0] != "LIVE"
    assert not any(method == "AddOrder" for method, _ in private.calls)


def test_real_buy_is_bounded_persisted_and_single_use(setup_live):
    state = activate(setup_live)
    pid = proposal(setup_live)
    response = approve(setup_live, pid, state["version"])
    assert response.status_code == 200, response.text
    assert response.json()["execution_status"] == "FILLED", (
        setup_live[1]
        .execute("SELECT execution_reasons FROM trade_proposals WHERE proposal_id=%s", (pid,))
        .fetchone()
    )
    client, db, _, _, private, _, _ = setup_live
    order = db.execute("SELECT environment, quantity, limit_price FROM order_intents").fetchone()
    assert order[0] == "LIVE" and order[1] * order[2] <= 100
    assert len(private.orders) == 1
    assert approve(setup_live, pid, state["version"]).status_code == 409
    assert len(private.orders) == 1
    assert client.get("/api/live").json()["orders"][0]["status"] == "FILLED"
    assert client.get("/api/proposals").json()["rows"][0]["execution"]["environment"] == "LIVE"


@pytest.mark.parametrize("failure", ["forbidden", "external_open", "stale", "mismatch"])
def test_unhealthy_real_accounts_never_submit(setup_live, failure):
    state = activate(setup_live)
    client, _, _, _, private, service, _ = setup_live
    if failure == "forbidden":
        private.forbidden = True
    elif failure == "external_open":
        private.external_open = True
    elif failure == "stale":
        service.provider.snapshot = replace(
            service.provider.snapshot, timestamp=datetime.now(UTC) - timedelta(minutes=2)
        )
    else:
        private.balances["ZUSD"] += Decimal(1)
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.status_code == 200
    assert response.json()["execution_status"] in {"BLOCKED", "FAILED"}
    assert private.orders == {}


def test_timeout_recovers_without_resubmission_and_requires_rearm(setup_live):
    state = activate(setup_live)
    client, db, _, _, private, service, _ = setup_live
    private.timeout = True
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.json()["execution_status"] == "UNKNOWN"
    client.portal.call(service.refresh)
    assert db.execute("SELECT status FROM order_intents").fetchone()[0] == "FILLED"
    assert sum(method == "AddOrder" for method, _ in private.calls) == 1
    assert client.get("/api/live").json()["state"] == "BLOCKED"
    assert client.get("/api/proposals").json()["rows"][0]["execution"]["status"] == "FILLED"


def test_live_approval_requires_mode_and_current_policy_version(setup_live):
    state = activate(setup_live)
    client, _, csrf, _, private, _, _ = setup_live
    pid = proposal(setup_live)
    for body in (
        {},
        {"environment": "PAPER"},
        {"environment": "LIVE", "live_version": state["version"] - 1},
    ):
        response = client.post(
            f"/api/proposals/{pid}/approve", json=body, headers={"X-CSRF-Token": csrf}
        )
        assert response.status_code == 409
    assert private.orders == {}


def test_pause_blocks_real_approval(setup_live):
    state = activate(setup_live)
    setup_live[1].execute("UPDATE control SET status='PAUSED'")
    result = approve(setup_live, proposal(setup_live), state["version"])
    assert result.json()["execution_status"] == "BLOCKED"
    assert setup_live[4].orders == {}


def test_real_sell_cannot_exceed_confirmed_spot_inventory(setup_live):
    state = activate(setup_live)
    assert (
        approve(setup_live, proposal(setup_live), state["version"]).json()["execution_status"]
        == "FILLED"
    )
    held = setup_live[4].balances["XXBT"]
    result = approve(setup_live, proposal(setup_live, "SHORT"), state["version"])
    assert result.json()["execution_status"] == "FILLED"
    sales = [
        body
        for method, body in setup_live[4].calls
        if method == "AddOrder" and body["type"] == "sell"
    ]
    assert len(sales) == 1 and Decimal(sales[0]["volume"]) <= held
    assert setup_live[4].balances["XXBT"] >= 0


def test_daily_loss_limit_is_persisted_and_cannot_be_reset_by_rearming(setup_live):
    activate(setup_live)
    client, db, csrf, _, private, service, body = setup_live
    db.execute(
        "INSERT INTO equity_snapshots(account_id, environment, equity, high_water_mark, "
        "recorded_at) "
        "SELECT 'live:' || connection_id, 'LIVE', 1100, 1100, "
        "now() - interval '1 hour' FROM live_control"
    )
    client.portal.call(service.refresh)
    assert client.get("/api/live").json()["state"] == "BLOCKED"
    response = client.post("/api/live/control", json=body, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 409
    assert "loss limit" in response.json()["detail"]
    assert private.orders == {}


@pytest.mark.parametrize("reason", ["venue_disabled", "insufficient_depth", "unavailable_fee"])
def test_missing_execution_evidence_blocks_the_real_gateway(setup_live, reason):
    state = activate(setup_live)
    client, _, _, _, private, service, _ = setup_live
    if reason == "venue_disabled":
        client.app.state.settings.live_capable = False
    elif reason == "insufficient_depth":
        original = service.provider.transport.get

        async def empty_book(path, params):
            if path.endswith("Depth"):
                return {"result": {"XXBTZUSD": {"asks": [], "bids": []}}}
            return await original(path, params)

        service.provider.transport.get = empty_book
    else:
        original = private.call

        async def missing_fee(method, params):
            if method == "TradeVolume":
                raise KrakenPrivateError("unavailable")
            return await original(method, params)

        private.call = missing_fee
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.json()["execution_status"] in {"BLOCKED", "FAILED"}
    assert private.orders == {}


def test_real_activation_cannot_bypass_owner_role_or_csrf(setup_live):
    client, db, csrf, _, private, _, body = setup_live
    assert client.post("/api/live/control", json=body).status_code == 403
    db.execute("UPDATE users SET role='VIEWER'")
    assert (
        client.post("/api/live/control", json=body, headers={"X-CSRF-Token": csrf}).status_code
        == 403
    )
    assert db.execute("SELECT count(*) FROM live_control").fetchone()[0] == 0
    assert private.orders == {}


def test_pause_just_before_network_submission_revokes_real_authorization(setup_live):
    state = activate(setup_live)
    db, private = setup_live[1], setup_live[4]
    original = private.call
    count = 0

    async def racing_pause(method, params):
        nonlocal count
        if method == "GetApiKeyInfo":
            count += 1
            if count == 2:
                db.execute("UPDATE control SET status='PAUSED'")
        return await original(method, params)

    private.call = racing_pause
    result = approve(setup_live, proposal(setup_live), state["version"])
    assert result.json()["execution_status"] == "REJECTED"
    assert private.orders == {}


def test_analyst_reads_only_sanitized_fresh_portfolio_context(setup_live):
    activate(setup_live)
    _, db, _, owner, _, _, _ = setup_live
    context = db.execute(
        "SELECT cash_usd, holdings, as_of FROM analyst_portfolio_context WHERE owner_id=%s",
        (owner,),
    ).fetchone()
    assert context[0] == 1000 and context[1] == {}
    assert datetime.now(UTC) - context[2] < timedelta(seconds=60)
    for table in (
        "provider_connections",
        "live_control",
        "kraken_nonces",
        "order_intents",
        "fills",
        "ledger_postings",
    ):
        assert (
            db.execute("SELECT has_table_privilege('wally_ai', %s, 'SELECT')", (table,)).fetchone()[
                0
            ]
            is False
        )
    assert (
        db.execute(
            "SELECT has_table_privilege('wally_ai', 'analyst_portfolio_context', 'SELECT')"
        ).fetchone()[0]
        is True
    )
    assert (
        db.execute(
            "SELECT has_table_privilege('wally_ai', 'analyst_portfolio_context', 'UPDATE')"
        ).fetchone()[0]
        is False
    )


def test_zero_core_mandate_blocks_a_real_buy(setup_live):
    state = activate(setup_live)
    setup_live[1].execute(
        "UPDATE ai_autonomy_control SET target_core_pct=0, target_growth_pct=1, "
        "target_speculative_pct=0"
    )
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.json()["execution_status"] == "BLOCKED"
    assert setup_live[4].orders == {}


def test_mandate_change_before_submission_revokes_the_order(setup_live):
    state = activate(setup_live)
    db, private = setup_live[1], setup_live[4]
    original = private.call
    count = 0

    async def change_mandate(method, params):
        nonlocal count
        if method == "GetApiKeyInfo":
            count += 1
            if count == 2:
                db.execute(
                    "UPDATE ai_autonomy_control SET target_core_pct=0.5, target_growth_pct=0.4, "
                    "target_speculative_pct=0.1"
                )
        return await original(method, params)

    private.call = change_mandate
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.json()["execution_status"] == "REJECTED"
    assert private.orders == {}


def test_live_activation_requires_recent_mfa(setup_live):
    client, db, csrf, _, private, _, body = setup_live
    db.execute("UPDATE sessions SET mfa_at=0")
    assert (
        client.post("/api/live/control", json=body, headers={"X-CSRF-Token": csrf}).status_code
        == 403
    )
    assert private.orders == {}


def test_quote_expiring_during_permission_check_prevents_submission(setup_live, monkeypatch):
    state = activate(setup_live)
    private, service = setup_live[4], setup_live[5]
    original = private.call
    count = 0

    async def slow_permission_check(method, params):
        nonlocal count
        if method == "GetApiKeyInfo":
            count += 1
            if count == 2:
                future = datetime.now(UTC) + timedelta(minutes=2)
                monkeypatch.setattr(service.clock, "now", lambda: future)
        return await original(method, params)

    private.call = slow_permission_check
    response = approve(setup_live, proposal(setup_live), state["version"])
    assert response.json()["execution_status"] == "REJECTED"
    assert private.orders == {}
