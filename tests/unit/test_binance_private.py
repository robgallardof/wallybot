"""Binance private transport: signing, permission gates, balances, fees and sanitized errors."""

from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from wallybot.exchanges.binance_private import (
    BinanceOrderNotFound,
    BinancePrivateError,
    SignedBinanceTransport,
    sign,
    spot_balances,
    taker_fee_rate,
    validate_restrictions,
)

SAFE = {
    "ipRestrict": True,
    "createTime": 1,
    "enableReading": True,
    "enableWithdrawals": False,
    "enableInternalTransfer": False,
    "enableMargin": False,
    "enableFutures": False,
    "permitsUniversalTransfer": False,
    "enableVanillaOptions": False,
    "enableFixApiTrade": False,
    "enableFixReadOnly": True,
    "enableSpotAndMarginTrading": True,
    "enablePortfolioMarginTrading": False,
}


def test_signature_matches_documented_reference_vector():
    secret = "NhqPtmdSJYdKjVHjA7PZj4Mge3R5YNiP1e3UZjInClVN65XAbvqqM6A7H5fATj0j"
    query = (
        "symbol=LTCBTC&side=BUY&type=LIMIT&timeInForce=GTC&quantity=1&price=0.1"
        "&recvWindow=5000&timestamp=1499827319559"
    )
    # Published golden value from Binance's signing guide, not computed by the implementation.
    assert sign(query, secret) == (
        "c8db56825ae71d6d79447849e617115f4a920fa2acdcab2b053c4b2838bd6b71"
    )


def test_safe_trade_only_key_is_accepted():
    validate_restrictions(SAFE)


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"enableWithdrawals": True}, "excessive permissions"),
        ({"enableInternalTransfer": True}, "excessive permissions"),
        ({"permitsUniversalTransfer": True}, "excessive permissions"),
        ({"enableMargin": True}, "excessive permissions"),
        ({"enableFutures": True}, "excessive permissions"),
        ({"enableSpotAndMarginTrading": False}, "reading and spot trading"),
        ({"ipRestrict": False}, "trusted IPs"),
        ({"enableWithdrawals": None}, "Cannot verify"),
    ],
)
def test_unsafe_or_incomplete_keys_fail_closed(change, expected):
    with pytest.raises(BinancePrivateError) as error:
        validate_restrictions({**SAFE, **change})
    assert expected in str(error.value)


def test_balances_keep_locked_funds_visible_and_require_spot_trading():
    account = {
        "accountType": "SPOT",
        "canTrade": True,
        "balances": [
            {"asset": "USDT", "free": "90", "locked": "10"},
            {"asset": "BNB", "free": "0", "locked": "0"},
        ],
    }
    assert spot_balances(account) == {"USDT": (Decimal("100"), Decimal("90"))}
    for broken in ({**account, "canTrade": False}, {**account, "accountType": "MARGIN"}):
        with pytest.raises(BinancePrivateError):
            spot_balances(broken)
    with pytest.raises(BinancePrivateError):
        spot_balances({**account, "balances": [{"asset": "BTC", "free": "-1", "locked": "0"}]})


def test_fee_rate_is_conservative_and_bounded():
    commission = {
        "standardCommission": {"maker": "0.001", "taker": "0.001", "buyer": "0", "seller": "0"},
        "taxCommission": {"maker": "0", "taker": "0.0001", "buyer": "0", "seller": "0"},
        "specialCommission": {"maker": "0", "taker": "0", "buyer": "0", "seller": "0"},
        "discount": {"enabledForAccount": True, "discount": "0.75"},
    }
    assert taker_fee_rate(commission) == Decimal("0.0011")
    with pytest.raises(BinancePrivateError):
        taker_fee_rate({})
    with pytest.raises(BinancePrivateError):
        taker_fee_rate(
            {"standardCommission": {"taker": "0.5", "buyer": "0", "seller": "0", "maker": "0"}}
        )


async def _call(respond, method="GET", path="/api/v3/account"):
    requests = []

    def handler(request):
        requests.append(request)
        return respond(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        transport = SignedBinanceTransport("test-key", "test-secret", client, lambda: 1700000000000)
        result = await transport.call(method, path, {"symbol": "BTCUSDT"})
    return result, requests


async def test_requests_are_signed_with_header_key_and_timestamp():
    result, requests = await _call(lambda request: httpx.Response(200, json={"ok": True}))
    assert result == {"ok": True}
    (request,) = requests
    assert request.headers["X-MBX-APIKEY"] == "test-key"
    query = urlsplit(str(request.url)).query
    unsigned, _, signature = query.rpartition("&signature=")
    assert signature == sign(unsigned, "test-secret")
    assert parse_qs(unsigned)["timestamp"] == ["1700000000000"]


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (401, {"code": -2015, "msg": "Invalid API-key, IP"}, "IP restriction"),
        (400, {"code": -2008, "msg": "Invalid Api-Key ID."}, "does not recognize this API key"),
        (400, {"code": -1022, "msg": "Signature"}, "Secret Key"),
        (400, {"code": -1021, "msg": "Timestamp"}, "clock"),
        (429, {"code": -1003, "msg": "Too many"}, "limiting"),
        (451, {"code": 0, "msg": "restricted location"}, "not available from this location"),
        (400, {"code": -2010, "msg": "Account has insufficient balance"}, "insufficient funds"),
        (400, {"code": -9999, "msg": "test-key secret payload"}, "rejected the private"),
        (503, None, "temporarily unavailable"),
    ],
)
async def test_provider_errors_are_explained_without_echoing_payloads(status, payload, expected):
    with pytest.raises(BinancePrivateError) as error:
        await _call(lambda request: httpx.Response(status, json=payload))
    assert expected in str(error.value)
    assert "test-key" not in str(error.value) and "test-secret" not in str(error.value)


async def test_missing_order_is_distinguished_for_reconciliation():
    with pytest.raises(BinanceOrderNotFound):
        await _call(
            lambda request: httpx.Response(
                400, json={"code": -2013, "msg": "Order does not exist."}
            ),
            path="/api/v3/order",
        )


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/sapi/v1/capital/withdraw/apply"),
        ("POST", "/sapi/v1/asset/transfer"),
        ("POST", "/sapi/v1/margin/loan"),
        ("GET", "/sapi/v1/capital/deposit/address"),
    ],
)
async def test_funding_and_margin_endpoints_are_unreachable(method, path):
    with pytest.raises(BinancePrivateError):
        await _call(lambda request: httpx.Response(200, json={}), method=method, path=path)


async def test_timestamps_follow_binance_server_time_when_the_local_clock_drifts():
    import time as clock

    from wallybot.exchanges import binance_private

    binance_private._SERVER_OFFSET.clear()
    skew = 30_000
    seen = []

    def handler(request):
        if request.url.path == "/api/v3/time":
            return httpx.Response(200, json={"serverTime": clock.time_ns() // 1_000_000 + skew})
        seen.append(int(parse_qs(urlsplit(str(request.url)).query)["timestamp"][0]))
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await SignedBinanceTransport("k", "s", client).call("GET", "/api/v3/account", {})
    local = clock.time_ns() // 1_000_000
    assert abs(seen[0] - (local + skew)) < 2_000
    binance_private._SERVER_OFFSET.clear()


async def test_timestamp_rejection_resyncs_the_offset_and_retries_once():
    from wallybot.exchanges import binance_private
    from wallybot.exchanges.private_errors import TransientExchangeError

    binance_private._SERVER_OFFSET.clear()
    calls = {"time": 0, "account": 0}

    def handler(request):
        if request.url.path == "/api/v3/time":
            calls["time"] += 1
            return httpx.Response(200, json={"serverTime": 1_700_000_000_000})
        calls["account"] += 1
        if calls["account"] == 1:
            return httpx.Response(400, json={"code": -1021, "msg": "Timestamp"})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await SignedBinanceTransport("k", "s", client).call("GET", "/api/v3/account", {})
    assert result == {"ok": True}
    assert calls == {"time": 2, "account": 2}
    binance_private._SERVER_OFFSET.clear()

    with pytest.raises(TransientExchangeError):
        await _call(lambda request: httpx.Response(429, json={"code": -1003, "msg": "Too many"}))
