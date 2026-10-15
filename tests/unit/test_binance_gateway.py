"""Binance gateway: bounded IOC submission, reconciliation and quote-currency fee normalization."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.binance_fake import FakeBinanceAccount
from wallybot.domain.execution import SubmissionOutcome, VenueOrderStatus
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import OrderIntent, OrderKind, OrderStatus, Side
from wallybot.exchanges.binance_gateway import BinanceSpotGateway
from wallybot.exchanges.binance_private import BinancePrivateError

NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
BTC = Instrument("binance", MarketType.SPOT, "BTC", "USDT")


def intent(side=Side.BUY, venue="binance", quantity="0.001", price="80000") -> OrderIntent:
    return OrderIntent(
        account_id="live:test",
        environment="LIVE",
        instrument=Instrument(venue, MarketType.SPOT, "BTC", "USDT"),
        side=side,
        kind=OrderKind.LIMIT,
        quantity=Decimal(quantity),
        limit_price=Decimal(price),
        decision_id=str(uuid4()),
        client_order_id=str(uuid4()),
        idempotency_key="proposal:test",
        risk_assessment_id=str(uuid4()),
        config_versions={"live": 1},
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=1),
        status=OrderStatus.VALIDATED,
    )


def gateway(account, order, authorized=True, now=NOW):
    async def load(_):
        return order

    async def authorize(_):
        return authorized

    return BinanceSpotGateway(account, load, lambda: now, authorize)


async def test_buy_is_a_bounded_ioc_limit_with_the_durable_client_identity():
    account, order = FakeBinanceAccount(), intent()
    result = await gateway(account, order).submit_order(order)

    assert result.outcome is SubmissionOutcome.ACCEPTED
    placed = next(params for method, _, params in account.calls if method == "POST")
    assert placed["timeInForce"] == "IOC" and placed["type"] == "LIMIT"
    assert placed["newClientOrderId"] == order.client_order_id
    assert placed["quantity"] == "0.001" and placed["price"] == "80000"


async def test_base_currency_buy_fee_is_booked_in_quote_without_changing_cash_spent():
    account, order = FakeBinanceAccount(), intent()
    venue = gateway(account, order)
    await venue.submit_order(order)

    lookup = await venue.lookup_order(order.client_order_id)
    (fill,) = await venue.list_fills(order.client_order_id)

    assert lookup.status is VenueOrderStatus.FILLED
    assert fill.quantity == Decimal("0.000999")  # BTC actually credited
    assert fill.fee_currency == "USDT" and fill.fee == Decimal("0.080000")
    assert fill.quantity * fill.price + fill.fee == Decimal("80")  # exact USDT spent
    assert account.balances["BTC"] == fill.quantity


async def test_fee_in_a_third_asset_is_refused_instead_of_misbooked():
    account, order = FakeBinanceAccount(), intent()
    account.fee_asset = "BNB"
    venue = gateway(account, order)
    await venue.submit_order(order)
    with pytest.raises(BinancePrivateError, match="BNB"):
        await venue.list_fills(order.client_order_id)


async def test_partial_ioc_is_a_terminal_cancellation_with_its_fill():
    account, order = FakeBinanceAccount(), intent()
    account.fill_ratio = Decimal("0.5")
    venue = gateway(account, order)
    await venue.submit_order(order)
    lookup = await venue.lookup_order(order.client_order_id)
    assert lookup.status is VenueOrderStatus.CANCELLED
    assert lookup.cumulative_filled_quantity == Decimal("0.0005")


async def test_lost_response_is_unknown_and_reconciles_without_resubmitting():
    account, order = FakeBinanceAccount(), intent()
    account.timeout = True
    venue = gateway(account, order)
    assert (await venue.submit_order(order)).outcome is SubmissionOutcome.UNKNOWN
    assert (await venue.lookup_order(order.client_order_id)).status is VenueOrderStatus.FILLED
    assert sum(method == "POST" for method, _, _ in account.calls) == 1


async def test_never_sent_order_is_not_found():
    account, order = FakeBinanceAccount(), intent()
    lookup = await gateway(account, order).lookup_order(order.client_order_id)
    assert lookup.status is VenueOrderStatus.NOT_FOUND


@pytest.mark.parametrize(
    "case", ["withdrawals", "other_venue", "revoked_authorization", "expired", "changed_order"]
)
async def test_unsafe_submissions_are_rejected_before_or_after_reaching_binance(case):
    account, order = FakeBinanceAccount(), intent()
    authorized = case != "revoked_authorization"
    if case == "withdrawals":
        account.restrictions["enableWithdrawals"] = True
    elif case == "other_venue":
        order = intent(venue="kraken")
    clock = NOW + timedelta(minutes=2) if case == "expired" else NOW
    venue = gateway(account, order, authorized, clock)
    if case == "changed_order":
        await venue.submit_order(order)
        account.orders[order.client_order_id]["origQty"] = "5"
        with pytest.raises(BinancePrivateError, match="differs"):
            await venue.lookup_order(order.client_order_id)
        return
    result = await venue.submit_order(order)
    assert result.outcome is SubmissionOutcome.REJECTED
    assert not any(method == "POST" for method, _, _ in account.calls)


async def test_fill_identity_is_stable_and_scoped_to_account_and_symbol():
    from dataclasses import replace

    account, order = FakeBinanceAccount(), intent()
    venue = gateway(account, order)
    await venue.submit_order(order)
    (first,) = await venue.list_fills(order.client_order_id)
    assert (await venue.list_fills(order.client_order_id))[0].fill_id == first.fill_id
    other_order = replace(order, account_id="live:another")
    (other,) = await gateway(account, other_order).list_fills(order.client_order_id)
    assert other.fill_id != first.fill_id
    assert len("ledger-" + first.fill_id) <= 64
    assert first.fill_id.startswith("binance-")


@pytest.mark.parametrize("field,value", [("price", "1"), ("timeInForce", "GTC")])
async def test_reconciliation_rejects_changed_price_or_time_in_force(field, value):
    account, order = FakeBinanceAccount(), intent()
    venue = gateway(account, order)
    await venue.submit_order(order)
    account.orders[order.client_order_id][field] = value
    with pytest.raises(BinancePrivateError, match="differs"):
        await venue.lookup_order(order.client_order_id)


async def test_duplicate_or_wrong_symbol_trade_evidence_is_rejected():
    account, order = FakeBinanceAccount(), intent()
    venue = gateway(account, order)
    await venue.submit_order(order)
    trades = account.trades[1]
    trades.append(dict(trades[0]))
    with pytest.raises(BinancePrivateError, match="scope"):
        await venue.list_fills(order.client_order_id)
    trades.pop()
    trades[0]["symbol"] = "ETHUSDT"
    with pytest.raises(BinancePrivateError, match="scope"):
        await venue.list_fills(order.client_order_id)


async def test_quote_total_and_executed_quantity_must_match_approved_trade_evidence():
    account, order = FakeBinanceAccount(), intent()
    venue = gateway(account, order)
    await venue.submit_order(order)
    original = account.orders[order.client_order_id]
    original["cummulativeQuoteQty"] = "1"
    with pytest.raises(BinancePrivateError, match="Incomplete"):
        await venue.list_fills(order.client_order_id)
    original["executedQty"] = "2"
    with pytest.raises(BinancePrivateError, match="exceeds"):
        await venue.lookup_order(order.client_order_id)
