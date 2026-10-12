from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from wallybot.domain.execution import SubmissionOutcome, VenueOrderStatus
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.exchanges.kraken_gateway import KrakenSpotGateway
from wallybot.exchanges.kraken_private import REQUIRED_PERMISSIONS, KrakenPrivateError

NOW = datetime(2026, 10, 8, tzinfo=UTC)


def intent(**overrides):
    result = OrderIntent(
        account_id="live:test",
        environment="LIVE",
        instrument=Instrument("kraken", MarketType.SPOT, "XBT", "USD"),
        side=Side.BUY,
        kind=OrderKind.LIMIT,
        quantity=Decimal("0.01"),
        limit_price=Decimal("60000"),
        decision_id="decision",
        client_order_id=str(uuid4()),
        idempotency_key="proposal:test",
        risk_assessment_id="risk",
        config_versions={"risk": 1},
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        status=OrderStatus.SUBMITTING,
    )
    return replace(result, **overrides)


class Transport:
    def __init__(self, order, *, timeout=False, forbidden=False):
        self.order = order
        self.timeout = timeout
        self.forbidden = forbidden
        self.calls = []

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "GetApiKeyInfo":
            return {
                "permissions": sorted(
                    REQUIRED_PERMISSIONS | ({"withdraw-funds"} if self.forbidden else set())
                )
            }
        if method == "AddOrder":
            if self.timeout:
                raise KrakenPrivateError("ambiguous")
            return {"txid": ["venue-order"]}
        if method == "OpenOrders":
            return {"open": {}}
        if method == "ClosedOrders":
            return {"closed": {"venue-order": self.order}, "count": 1}
        if method == "QueryTrades":
            return {
                "trade-1": {
                    "ordertxid": "venue-order",
                    "type": "buy",
                    "vol": "0.01",
                    "price": "60000",
                    "fee": "0.6",
                    "time": "1791417600.123456",
                    "margin": "0",
                }
            }
        raise AssertionError(method)


def gateway(order_intent, **kwargs):
    row = {
        "cl_ord_id": order_intent.client_order_id,
        "descr": {"pair": "XBTUSD", "type": "buy"},
        "vol": "0.01",
        "vol_exec": "0.01",
        "price": "60000",
        "status": "closed",
        "trades": ["trade-1"],
    }
    transport = Transport(row, **kwargs)

    async def load(client_id):
        assert client_id == order_intent.client_order_id
        return order_intent

    return KrakenSpotGateway(transport, load, lambda: NOW), transport


@pytest.mark.asyncio
async def test_live_limit_submission_is_bounded_and_spot_only():
    order = intent()
    adapter, transport = gateway(order)
    result = await adapter.submit_order(order)
    assert result.outcome is SubmissionOutcome.ACCEPTED
    method, body = transport.calls[-1]
    assert method == "AddOrder"
    assert body["timeinforce"] == "IOC" and body["price"] == "60000"
    assert body["cl_ord_id"] == order.client_order_id
    assert "leverage" not in body and "close" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "override",
    [
        {"environment": "PAPER"},
        {"created_at": NOW - timedelta(minutes=1), "expires_at": NOW},
        {"client_order_id": "bad-id"},
    ],
)
async def test_ineligible_intent_never_reaches_submission(override):
    order = intent(**override)
    adapter, transport = gateway(order)
    assert (await adapter.submit_order(order)).outcome is SubmissionOutcome.REJECTED
    assert not any(method == "AddOrder" for method, _ in transport.calls)


@pytest.mark.asyncio
async def test_excessive_permissions_block_submission():
    order = intent()
    adapter, transport = gateway(order, forbidden=True)
    assert (await adapter.submit_order(order)).outcome is SubmissionOutcome.REJECTED
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_accept_then_timeout_reconciles_original_identity_without_resubmit():
    order = intent()
    adapter, transport = gateway(order, timeout=True)
    assert (await adapter.submit_order(order)).outcome is SubmissionOutcome.UNKNOWN
    lookup = await adapter.lookup_order(order.client_order_id)
    assert lookup.status is VenueOrderStatus.FILLED
    fills = await adapter.list_fills(order.client_order_id)
    assert len(fills) == 1 and fills[0].fee == Decimal("0.6")
    assert fills[0].filled_at.microsecond == 123456
    assert sum(method == "AddOrder" for method, _ in transport.calls) == 1


@pytest.mark.asyncio
async def test_mismatched_exchange_order_fails_closed():
    order = intent()
    adapter, transport = gateway(order)
    transport.order["vol"] = "0.02"
    with pytest.raises(KrakenPrivateError):
        await adapter.lookup_order(order.client_order_id)


@pytest.mark.asyncio
async def test_lookup_uses_documented_client_filter_when_response_omits_optional_identity():
    order = intent()
    adapter, transport = gateway(order)
    del transport.order["cl_ord_id"]
    assert (await adapter.lookup_order(order.client_order_id)).status is VenueOrderStatus.FILLED
    for method, params in transport.calls:
        if method in {"OpenOrders", "ClosedOrders"}:
            assert params["cl_ord_id"] == order.client_order_id
