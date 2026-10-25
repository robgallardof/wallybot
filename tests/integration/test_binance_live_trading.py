"""Binance real mode with scripted private semantics and real PostgreSQL. Never funded keys."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

import pytest

from tests.binance_fake import FakeBinanceAccount
from tests.integration.test_connection_routes import enroll
from tests.integration.test_live_trading import approve, proposal
from wallybot.exchanges.binance import BinanceExchange

pytestmark = pytest.mark.integration


class SystemClock:
    def now(self):
        return datetime.now(UTC)


class PublicBinance:
    """Recorded-shape public responses: 20 closed hourly BTCUSDT candles and a tight book."""

    async def get(self, path, params):
        if path == "/api/v3/exchangeInfo":
            return {
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "status": "TRADING",
                        "baseAsset": "BTC",
                        "quoteAsset": "USDT",
                        "isSpotTradingAllowed": True,
                        "filters": [
                            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                            {
                                "filterType": "LOT_SIZE",
                                "minQty": "0.00001000",
                                "stepSize": "0.00001000",
                            },
                            {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
                        ],
                    }
                ]
            }
        if path == "/api/v3/klines":
            hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
            rows = []
            for i in range(20):
                open_time = hour - timedelta(hours=20 - i)
                close = str(50000 + i * 100)
                rows.append([int(open_time.timestamp() * 1000), close, close, close, close, "10"])
            return rows
        if path == "/api/v3/ticker/bookTicker":
            return {"bidPrice": "51895.00", "askPrice": "51905.00"}
        if path == "/api/v3/depth":
            return {"bids": [["51895.00", "10"]], "asks": [["51905.00", "10"]]}
        raise AssertionError(path)


@pytest.fixture
def setup_binance(client, settings, db, monkeypatch):
    monkeypatch.setattr(client.app.state.settings, "live_capable", True)
    db.execute("UPDATE control SET environment='OBSERVE'")
    db.execute("DELETE FROM live_control")
    db.execute(
        "UPDATE ai_autonomy_control SET target_core_pct=0.70, target_growth_pct=0.20, "
        "target_speculative_pct=0.10"
    )
    db.execute(
        "TRUNCATE equity_snapshots, breakers, ledger_postings, ledger_transactions, "
        "ledger_accounts, fills, order_transitions, order_intents, shadow_decisions, "
        "trade_proposals, analyst_portfolio_context CASCADE"
    )
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    owner = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
    account = FakeBinanceAccount()
    client.app.state.binance_private_factory = lambda key, secret: account
    service = client.app.state.live_trading
    service.binance_provider = BinanceExchange(SystemClock(), transport=PublicBinance())
    yield client, db, csrf, owner, account, service
    # The control row is shared across tests; never leave the next test in LIVE.
    db.execute("UPDATE control SET environment='OBSERVE'")
    db.execute("DELETE FROM live_control")


def link(setup):
    client, _, csrf, *_ = setup
    return client.post(
        "/api/connections",
        headers={"X-CSRF-Token": csrf},
        json={
            "provider": "BINANCE",
            "label": "Binance real",
            "mode": "TRADE_ONLY",
            "api_key": "synthetic-binance-key",
            "api_secret": "synthetic-binance-secret",
        },
    )


def activate(setup):
    client, _, csrf, *_ = setup
    connection = link(setup)
    assert connection.status_code == 200, connection.text
    response = client.post(
        "/api/live/control",
        headers={"X-CSRF-Token": csrf},
        json={
            "connection_id": connection.json()["id"],
            "enabled": True,
            "confirmation": "LIVE",
            "max_order_usd": "100",
            "max_daily_loss_usd": "10",
            "max_total_usd": "200",
            "slippage_pct": "0.005",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def binance_proposal(setup, direction="LONG"):
    client, db, csrf, owner, account, service = setup
    pid = proposal((client, db, csrf, owner, None, service, None), direction)
    db.execute(
        "UPDATE trade_proposals SET venue='binance', base='BTC', quote='USDT' WHERE proposal_id=%s",
        (pid,),
    )
    return pid


def approve_live(setup, pid, version):
    client, db, csrf, owner, _, service = setup
    return approve((client, db, csrf, owner, None, service, None), pid, version)


def test_linking_checks_permissions_and_balances_without_trading(setup_binance):
    _, db, _, _, account, _ = setup_binance
    response = link(setup_binance)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "HEALTHY"
    assert "synthetic" not in response.text
    assert [path for _, path, _ in account.calls] == [
        "/sapi/v1/account/apiRestrictions",
        "/api/v3/account",
    ]
    assert db.execute("SELECT environment FROM control").fetchone()[0] != "LIVE"


@pytest.mark.parametrize(
    "change,message",
    [
        ({"enableWithdrawals": True}, "excessive permissions"),
        ({"ipRestrict": False}, "trusted IPs"),
    ],
)
def test_unsafe_binance_keys_are_rejected_with_an_explanation(setup_binance, change, message):
    _, db, _, _, account, _ = setup_binance
    account.restrictions.update(change)
    response = link(setup_binance)
    assert response.status_code == 409
    assert message in response.json()["detail"]
    assert db.execute("SELECT count(*) FROM provider_connections").fetchone()[0] == 0


def test_activation_shows_venue_and_records_usdt_opening_balance(setup_binance):
    state = activate(setup_binance)
    assert state["state"] == "READY" and state["venue"] == "binance"
    assert state["cash_currency"] == "USDT"
    assert {row["asset"]: row["amount"] for row in state["balances"]} == {"USDT": "1000"}
    _, db, *_ = setup_binance
    assert db.execute("SELECT venue FROM analyst_portfolio_context").fetchone()[0] == "binance"


def test_real_buy_then_sell_reconcile_exactly_with_binance_fees(setup_binance):
    state = activate(setup_binance)
    client, db, _, _, account, service = setup_binance

    bought = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    assert bought.status_code == 200, bought.text
    assert bought.json()["execution_status"] == "FILLED", bought.json()
    placed = [params for method, _, params in account.calls if method == "POST"]
    assert len(placed) == 1 and placed[0]["timeInForce"] == "IOC"
    assert Decimal(placed[0]["quantity"]) * Decimal(placed[0]["price"]) <= 100

    # The fee was taken in BTC; the ledger must still match Binance to the satoshi.
    client.portal.call(service.refresh)
    live = client.get("/api/live").json()
    assert live["state"] == "READY", live["reason"]
    ledger = {row["asset"]: Decimal(row["amount"]) for row in live["balances"]}
    assert ledger["BTC"] == account.balances["BTC"]
    assert ledger["USDT"] == account.balances["USDT"]

    sold = approve_live(setup_binance, binance_proposal(setup_binance, "SHORT"), state["version"])
    assert sold.json()["execution_status"] == "FILLED", sold.json()
    client.portal.call(service.refresh)
    assert client.get("/api/live").json()["state"] == "READY"
    assert db.execute("SELECT count(*) FROM fills WHERE environment='LIVE'").fetchone()[0] == 2


def test_small_risk_sizes_lift_to_the_venue_minimum_and_sales_leave_no_dust(setup_binance):
    # A 0.5% confidence sizes the order at ~3.5 USDT, under Binance's 5 USDT minimum notional.
    state = activate(setup_binance)
    client, db, _, _, account, service = setup_binance
    pid = binance_proposal(setup_binance)
    db.execute("UPDATE trade_proposals SET confidence=0.005 WHERE proposal_id=%s", (pid,))
    bought = approve_live(setup_binance, pid, state["version"])
    assert bought.json()["execution_status"] == "FILLED", bought.json()
    buy = [params for method, _, params in account.calls if method == "POST"][-1]
    notional = Decimal(buy["quantity"]) * Decimal(buy["price"])
    assert Decimal("5.5") <= notional < 6

    client.portal.call(service.refresh)
    held = account.balances["BTC"]
    pid = binance_proposal(setup_binance, "SHORT")
    db.execute("UPDATE trade_proposals SET confidence=0.5 WHERE proposal_id=%s", (pid,))
    sold = approve_live(setup_binance, pid, state["version"])
    assert sold.json()["execution_status"] == "FILLED", sold.json()
    sale = [params for method, _, params in account.calls if method == "POST"][-1]
    # Selling half (~2.5 USDT) is under the minimum and would strand dust: it closes it all.
    assert sale["side"] == "SELL"
    assert Decimal(sale["quantity"]) == held.quantize(Decimal("0.00001"), ROUND_DOWN)


def test_one_asset_never_grows_beyond_the_per_order_limit(setup_binance):
    state = activate(setup_binance)
    _, _, _, _, account, service = setup_binance
    first = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    assert first.json()["execution_status"] == "FILLED", first.json()
    setup_binance[0].portal.call(service.refresh)
    second = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    spent = sum(
        Decimal(params["quantity"]) * Decimal(params["price"])
        for method, _, params in account.calls
        if method == "POST"
    )
    # max_order_usd is 100: the second BTC buy may only top the position up to that size.
    assert second.json()["execution_status"] in {"FILLED", "BLOCKED"}
    assert spent <= 100


def test_kraken_proposals_cannot_execute_on_a_binance_account(setup_binance):
    state = activate(setup_binance)
    client, db, csrf, owner, account, service = setup_binance
    pid = proposal((client, db, csrf, owner, None, service, None))  # Kraken XBT/USD analysis
    response = approve_live(setup_binance, pid, state["version"])
    assert response.json()["execution_status"] == "BLOCKED"
    reasons = db.execute(
        "SELECT execution_reasons FROM trade_proposals WHERE proposal_id=%s", (pid,)
    ).fetchone()[0]
    assert "another exchange" in str(reasons)
    assert not any(method == "POST" for method, _, _ in account.calls)


@pytest.mark.parametrize("base", ["OP", "BNB", "XYZ"])
def test_untradeable_pairs_are_refused_without_freezing_live(setup_binance, base):
    # OP: curated but missing from the venue listing; BNB: excluded asset; XYZ: unknown.
    state = activate(setup_binance)
    client, db, _, _, account, _ = setup_binance
    pid = binance_proposal(setup_binance)
    db.execute("UPDATE trade_proposals SET base=%s WHERE proposal_id=%s", (base, pid))
    response = approve_live(setup_binance, pid, state["version"])
    assert response.json()["execution_status"] == "BLOCKED", response.json()
    assert client.get("/api/live").json()["state"] == "READY"
    assert not any(method == "POST" for method, _, _ in account.calls)


@pytest.mark.parametrize("failure", ["withdrawals_enabled", "external_open", "bnb"])
def test_unhealthy_binance_accounts_never_submit(setup_binance, failure):
    state = activate(setup_binance)
    _, _, _, _, account, _ = setup_binance
    if failure == "withdrawals_enabled":
        account.restrictions["enableWithdrawals"] = True
    elif failure == "external_open":
        account.external_open = True
    else:
        account.balances["BNB"] = Decimal("0.01")
    response = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    assert response.json()["execution_status"] in {"BLOCKED", "FAILED"}
    assert not any(method == "POST" for method, _, _ in account.calls)


def test_external_binance_activity_is_adopted_instead_of_blocking(setup_binance):
    from wallybot.application.live_trading import BALANCE_DRIFT

    activate(setup_binance)
    client, db, _, _, account, service = setup_binance
    adjustments = "SELECT count(*) FROM ledger_transactions WHERE reason='LIVE_EXTERNAL_ADJUSTMENT'"
    # A manual deposit/buy on Binance, plus a block left by the code that used to latch on it.
    account.balances["USDT"] += Decimal(1)
    client.portal.call(service.latch, BALANCE_DRIFT)
    client.portal.call(service.refresh)
    live = client.get("/api/live").json()
    assert live["state"] == "READY" and live["reason"] == ""
    assert db.execute(adjustments).fetchone()[0] == 1
    # The ledger now matches, so the next sync adopts nothing more.
    client.portal.call(service.refresh)
    assert db.execute(adjustments).fetchone()[0] == 1


def test_failed_reactivation_keeps_a_live_account_enabled(setup_binance):
    state = activate(setup_binance)
    client, db, csrf, _, account, _ = setup_binance
    account.external_open = True
    # Saving limits / re-activating while the account cannot be verified must not turn LIVE off.
    response = client.post(
        "/api/live/control",
        headers={"X-CSRF-Token": csrf},
        json={
            "connection_id": state["connection_id"],
            "enabled": True,
            "confirmation": "LIVE",
            "max_order_usd": "100",
            "max_daily_loss_usd": "10",
            "max_total_usd": "200",
            "slippage_pct": "0.005",
        },
    )
    assert response.status_code == 409, response.text
    live = client.get("/api/live").json()
    assert live["enabled"] and live["state"] == "BLOCKED"
    assert db.execute("SELECT environment FROM control").fetchone()[0] == "LIVE"


def test_positions_report_entry_of_coins_bought_outside_wallybot(setup_binance):
    activate(setup_binance)
    client, _, _, _, account, service = setup_binance
    bought = datetime.now(UTC) - timedelta(days=3)
    account.balances["BTC"] = Decimal("0.5")
    account.manual_trades.append(
        {
            "symbol": "BTCUSDT",
            "price": "2000",
            "qty": "0.5",
            "commission": "0.5",
            "commissionAsset": "USDT",
            "time": int(bought.timestamp() * 1000),
            "isBuyer": True,
        }
    )
    client.portal.call(service.refresh)
    view = client.get("/api/live/positions").json()
    btc = next(row for row in view["positions"] if row["asset"] == "BTC")
    assert Decimal(btc["average_price"]) == 2000 and btc["source"] == "exchange"
    assert datetime.fromisoformat(btc["held_since"]) == bought.replace(
        microsecond=bought.microsecond // 1000 * 1000
    )
    price = Decimal(btc["price"])
    assert Decimal(btc["pnl"]) == (price - 2000) * Decimal("0.5")
    history = client.get("/api/live/positions/BTC/history").json()
    assert history["timeframe"] == "1h" and history["average_price"] == btc["average_price"]
    assert history["points"]
    assert client.get("/api/live/positions/DOGE/history").status_code == 404
    # Unchanged holdings are not re-read from Binance on every sync.
    calls = sum(path == "/api/v3/myTrades" for _, path, _ in account.calls)
    client.portal.call(service.refresh)
    assert sum(path == "/api/v3/myTrades" for _, path, _ in account.calls) == calls


def test_lost_binance_response_reconciles_without_resubmission(setup_binance):
    state = activate(setup_binance)
    client, db, _, _, account, service = setup_binance
    account.timeout = True
    response = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    assert response.json()["execution_status"] == "UNKNOWN"
    client.portal.call(service.refresh)
    assert db.execute("SELECT status FROM order_intents").fetchone()[0] == "FILLED"
    assert sum(method == "POST" for method, _, _ in account.calls) == 1


def test_dashboard_reports_binance_public_and_real_venues(setup_binance):
    client, *_ = setup_binance
    assert client.get("/api/dashboard").json()["exchange"] == "BINANCE_PUBLIC_DATA"
    assert client.get("/api/system").json()["exchange"] == "BINANCE_PUBLIC_DATA"
    activate(setup_binance)
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["exchange"] == "BINANCE_SPOT_REAL"
    assert dashboard["trading_available"] is True


def test_binance_paper_approval_spends_usdt_and_never_submits_to_private_api(setup_binance):
    from wallybot.exchanges.venue_routing import VenueRoutedMarketData

    client, db, csrf, _, account, service = setup_binance
    db.execute("UPDATE control SET environment='PAPER'")
    market = service.binance_provider
    client.app.state.market_overview.keywords["provider"] = market
    client.app.state.paper_ai.gateway.market_data = market
    client.app.state.portfolio_market_provider = VenueRoutedMarketData({"binance": market})
    funded = client.post(
        "/api/portfolio/ai/fund", json={"amount": "100000"}, headers={"X-CSRF-Token": csrf}
    )
    assert funded.status_code == 201, funded.text
    assert funded.json()["balances"][0]["currency"] == "USDT"
    pid = binance_proposal(setup_binance)
    approved = client.post(f"/api/proposals/{pid}/approve", json={}, headers={"X-CSRF-Token": csrf})
    assert approved.status_code == 200, approved.text
    assert approved.json()["execution_status"] == "FILLED", approved.json()
    assert db.execute("SELECT environment, venue, quote FROM fills").fetchall() == [
        ("PAPER", "binance", "USDT")
    ]
    assert not any(method == "POST" for method, _, _ in account.calls)
    view = client.get("/api/portfolio/ai").json()
    assert view["proposal_history"][0]["quote_source"] == "binance"


def test_scheduled_report_resolves_real_binance_account_and_fees(setup_binance):
    from wallybot.application.telegram_report_job import run_telegram_report_tick
    from wallybot.domain.notification_throttle import NotificationThrottle
    from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository

    state = activate(setup_binance)
    client, db, _, owner, account, service = setup_binance
    approved = approve_live(setup_binance, binance_proposal(setup_binance), state["version"])
    assert approved.json()["execution_status"] == "FILLED"
    client.portal.call(service.refresh)
    db.execute("TRUNCATE telegram_reports")

    class Reports:
        def __init__(self):
            self.texts = []

        async def post_form(self, url, form):
            self.texts.append(form["text"])

    transport = Reports()

    async def run():
        async with client.app.state.sessions.begin() as session:
            await TelegramConfigRepository(session).upsert(
                client.app.state.auth.crypto.encrypt("synthetic-report-token"), 42, True
            )
        await run_telegram_report_tick(
            client.app.state.sessions,
            client.app.state.auth.crypto,
            transport,
            NotificationThrottle(),
            "paper:" + owner,
            "PAPER",
            datetime.now(UTC),
            owner_id=owner,
            language="es",
        )

    try:
        client.portal.call(run)
    finally:
        db.execute(
            "UPDATE telegram_config SET enabled=false, encrypted_bot_token=NULL, chat_id=NULL"
        )
    assert len(transport.texts) == 2
    fee = db.execute("SELECT sum(fee) FROM fills WHERE environment='LIVE'").fetchone()[0]
    assert fee > 0
    for text in transport.texts:
        assert "Modo: LIVE" in text and "Exchange: Binance" in text
        assert f"Costes: {fee} USDT" in text
        assert "Conciliación: verificada" in text
        assert "Fase" not in text and "PENDING.md" not in text
    assert sum(method == "POST" for method, _, _ in account.calls) == 1


def test_scheduled_report_does_not_use_another_operators_live_account(setup_binance):
    from wallybot.application.telegram_report_job import run_telegram_report_tick
    from wallybot.domain.notification_throttle import NotificationThrottle

    activate(setup_binance)
    client, db, *_ = setup_binance
    db.execute("TRUNCATE telegram_reports")

    class NoDelivery:
        async def post_form(self, url, form):
            raise AssertionError("Foreign account report must not be sent")

    async def run():
        await run_telegram_report_tick(
            client.app.state.sessions,
            client.app.state.auth.crypto,
            NoDelivery(),
            NotificationThrottle(),
            "paper:another",
            "PAPER",
            datetime.now(UTC),
            owner_id="another",
            language="es",
        )

    client.portal.call(run)
    assert db.execute("SELECT count(*) FROM telegram_reports").fetchone()[0] == 0


def test_transient_binance_failures_only_block_after_repeating(setup_binance, monkeypatch):
    from wallybot.application.live_trading import TRANSIENT_FAILURES_BEFORE_BLOCK
    from wallybot.exchanges.binance_private import _UNREACHABLE, BinanceTransientError

    activate(setup_binance)
    client, _, _, _, account, service = setup_binance
    original = account.call

    async def flaky(method, path, params):
        raise BinanceTransientError(_UNREACHABLE)

    monkeypatch.setattr(account, "call", flaky)
    for _ in range(TRANSIENT_FAILURES_BEFORE_BLOCK - 1):
        client.portal.call(service.refresh)
        assert client.get("/api/live").json()["state"] == "READY"

    # A success resets the streak, so isolated hiccups never accumulate into a block.
    monkeypatch.setattr(account, "call", original)
    client.portal.call(service.refresh)
    monkeypatch.setattr(account, "call", flaky)
    for _ in range(TRANSIENT_FAILURES_BEFORE_BLOCK - 1):
        client.portal.call(service.refresh)
    assert client.get("/api/live").json()["state"] == "READY"

    client.portal.call(service.refresh)
    live = client.get("/api/live").json()
    assert live["state"] == "BLOCKED" and "could not be reached" in live["reason"]

    # Once Binance answers again the monitor re-arms LIVE without operator action.
    monkeypatch.setattr(account, "call", original)
    client.portal.call(service.refresh)
    live = client.get("/api/live").json()
    assert live["state"] == "READY" and live["reason"] == ""


def test_rejected_key_rearms_once_binance_accepts_it_again(setup_binance):
    from wallybot.exchanges.binance_private import explain_binance_error

    activate(setup_binance)
    client, _, _, _, _, service = setup_binance
    # e.g. the public IP changed and the operator then allowed the new one on Binance.
    client.portal.call(service.latch, str(explain_binance_error(401, {"code": -2015})))
    client.portal.call(service.refresh)
    live = client.get("/api/live").json()
    assert live["state"] == "READY" and live["reason"] == ""


def test_non_transient_blocks_stay_until_the_operator_rearms(setup_binance, monkeypatch):
    activate(setup_binance)
    client, _, _, _, _, service = setup_binance
    client.portal.call(
        service.latch, "Real account synchronization failed; no new trades are allowed"
    )
    client.portal.call(service.refresh)
    # The healthy sync must not clear a block that needs a human to review the account.
    assert client.get("/api/live").json()["state"] == "BLOCKED"
