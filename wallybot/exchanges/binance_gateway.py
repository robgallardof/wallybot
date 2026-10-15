"""Binance spot order gateway with durable client identities and reconcile-before-retry semantics.

Mirrors `kraken_gateway.py`: one LIMIT IOC order per approved intent, no automatic resubmission,
and every provider error after the request leaves the outcome UNKNOWN for reconciliation.

Binance deducts a BUY fee from the asset received. Fills are normalized so accounting stays in the
quote currency: quantity is the base actually credited and the fee is its quote-currency value at
the trade price. Cash (quantity * price + fee) still equals the exact quote amount Binance spent.
Fees charged in any third asset (for example BNB) are rejected rather than mis-booked.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from wallybot.domain.execution import (
    CancelOutcome,
    CancelResult,
    Fill,
    OrderLookup,
    SubmissionOutcome,
    SubmissionResult,
    VenueOrderStatus,
)
from wallybot.domain.market import MarketType
from wallybot.domain.order import OrderIntent, OrderKind, Side
from wallybot.exchanges.binance_private import (
    BinanceOrderNotFound,
    BinancePrivateError,
    BinancePrivateTransport,
    validate_restrictions,
)

_STATUS = {
    "NEW": VenueOrderStatus.ACKNOWLEDGED,
    "PENDING_NEW": VenueOrderStatus.ACKNOWLEDGED,
    "PARTIALLY_FILLED": VenueOrderStatus.PARTIALLY_FILLED,
    "PENDING_CANCEL": VenueOrderStatus.PARTIALLY_FILLED,
    "FILLED": VenueOrderStatus.FILLED,
    "CANCELED": VenueOrderStatus.CANCELLED,
    "EXPIRED": VenueOrderStatus.CANCELLED,
    "EXPIRED_IN_MATCH": VenueOrderStatus.CANCELLED,
    "REJECTED": VenueOrderStatus.REJECTED,
}


def _decimal(value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BinancePrivateError("Invalid Binance order evidence") from None
    if not number.is_finite() or number < 0:
        raise BinancePrivateError("Invalid Binance order evidence")
    return number


class BinanceSpotGateway:
    def __init__(
        self,
        transport: BinancePrivateTransport,
        load_intent: Callable[[str], Awaitable[OrderIntent]],
        now: Callable[[], datetime],
        authorize: Callable[[OrderIntent], Awaitable[bool]] | None = None,
    ) -> None:
        self.transport = transport
        self.load_intent = load_intent
        self.now = now
        self.authorize = authorize

    @staticmethod
    def _symbol(intent: OrderIntent) -> str:
        return intent.instrument.base + intent.instrument.quote

    async def submit_order(self, intent: OrderIntent) -> SubmissionResult:
        if (
            intent.environment != "LIVE"
            or intent.instrument.venue != "binance"
            or intent.instrument.market_type != MarketType.SPOT
            or intent.kind is not OrderKind.LIMIT
            or intent.limit_price is None
        ):
            return SubmissionResult(
                SubmissionOutcome.REJECTED, reason="Only LIVE Binance spot limit intents"
            )
        if intent.expires_at <= self.now():
            return SubmissionResult(SubmissionOutcome.REJECTED, reason="Intent expired")
        try:
            UUID(intent.client_order_id)
            validate_restrictions(
                await self.transport.call("GET", "/sapi/v1/account/apiRestrictions", {})
            )
        except (ValueError, BinancePrivateError):
            return SubmissionResult(
                SubmissionOutcome.REJECTED, reason="Invalid identity or key permissions"
            )
        params = {
            "symbol": self._symbol(intent),
            "side": intent.side.value,
            "type": "LIMIT",
            "timeInForce": "IOC",
            "quantity": format(intent.quantity, "f"),
            "price": format(intent.limit_price, "f"),
            "newClientOrderId": intent.client_order_id,
            "newOrderRespType": "ACK",
        }
        try:
            if intent.expires_at <= self.now() or (
                self.authorize is not None and not await self.authorize(intent)
            ):
                return SubmissionResult(
                    SubmissionOutcome.REJECTED, reason="Execution authorization changed"
                )
            result = await self.transport.call("POST", "/api/v3/order", params)
            if (
                not isinstance(result, dict)
                or result.get("clientOrderId") != intent.client_order_id
                or not isinstance(result.get("orderId"), int)
            ):
                raise BinancePrivateError("Invalid order response")
            return SubmissionResult(
                SubmissionOutcome.ACCEPTED, venue_order_id=str(result["orderId"])
            )
        except BinancePrivateError:
            # A provider error can follow acceptance. No retry, even for apparent rejection.
            return SubmissionResult(
                SubmissionOutcome.UNKNOWN, reason="Submission requires reconciliation"
            )

    async def _find(self, client_order_id: str) -> tuple[OrderIntent, dict[str, Any]] | None:
        intent = await self.load_intent(client_order_id)
        if intent.environment != "LIVE" or intent.instrument.venue != "binance":
            raise BinancePrivateError("Order scope mismatch")
        try:
            order = await self.transport.call(
                "GET",
                "/api/v3/order",
                {"symbol": self._symbol(intent), "origClientOrderId": client_order_id},
            )
        except BinanceOrderNotFound:
            return None
        if (
            not isinstance(order, dict)
            or order.get("clientOrderId") != client_order_id
            or order.get("symbol") != self._symbol(intent)
            or order.get("side") != intent.side.value
            or order.get("type") != "LIMIT"
            or order.get("timeInForce") != "IOC"
            or _decimal(order.get("price")) != intent.limit_price
            or _decimal(order.get("origQty")) != intent.quantity
        ):
            raise BinancePrivateError("Exchange order differs from approved intent")
        return intent, order

    async def lookup_order(self, client_order_id: str) -> OrderLookup:
        found = await self._find(client_order_id)
        if found is None:
            return OrderLookup(VenueOrderStatus.NOT_FOUND, Decimal(0), None)
        intent, order = found
        executed = _decimal(order.get("executedQty"))
        if executed > intent.quantity:
            raise BinancePrivateError("Executed quantity exceeds approved intent")
        state = _STATUS.get(str(order.get("status")))
        if state is None:
            raise BinancePrivateError("Unknown exchange order status")
        if state is VenueOrderStatus.ACKNOWLEDGED and executed:
            state = VenueOrderStatus.PARTIALLY_FILLED
        if state is VenueOrderStatus.REJECTED and executed:
            raise BinancePrivateError("Rejected order reports executed quantity")
        quote = _decimal(order.get("cummulativeQuoteQty"))
        average = quote / executed if executed and quote else None
        return OrderLookup(state, executed, average, str(order.get("orderId")))

    async def list_fills(self, client_order_id: str) -> tuple[Fill, ...]:
        found = await self._find(client_order_id)
        if found is None:
            return ()
        intent, order = found
        executed = _decimal(order.get("executedQty"))
        if not executed:
            return ()
        trades = await self.transport.call(
            "GET",
            "/api/v3/myTrades",
            {"symbol": self._symbol(intent), "orderId": str(order["orderId"])},
        )
        if not isinstance(trades, list):
            raise BinancePrivateError("Incomplete trade evidence")
        base, quote = intent.instrument.base, intent.instrument.quote
        buy = intent.side is Side.BUY
        fills = []
        executed_by_trades = Decimal(0)
        quote_by_trades = Decimal(0)
        seen: set[int] = set()
        for trade in trades:
            if (
                not isinstance(trade, dict)
                or trade.get("orderId") != order["orderId"]
                or trade.get("isBuyer") is not buy
                or trade.get("symbol") != self._symbol(intent)
                or type(trade.get("id")) is not int
                or trade["id"] < 0
                or trade["id"] in seen
            ):
                raise BinancePrivateError("Trade evidence scope mismatch")
            seen.add(trade["id"])
            quantity = _decimal(trade.get("qty"))
            price = _decimal(trade.get("price"))
            commission = _decimal(trade.get("commission"))
            asset = trade.get("commissionAsset")
            if not quantity or not price:
                raise BinancePrivateError("Invalid Binance order evidence")
            if intent.limit_price is None or (
                price > intent.limit_price if buy else price < intent.limit_price
            ):
                raise BinancePrivateError("Fill price exceeds approved limit")
            executed_by_trades += quantity
            quote_by_trades += quantity * price
            if asset == quote or not commission:
                credited, fee = quantity, commission
            elif asset == base and buy and commission < quantity:
                credited, fee = quantity - commission, commission * price
            else:
                raise BinancePrivateError(
                    "Binance charged the fee in another asset; turn off paying fees with BNB"
                )
            fills.append(
                Fill(
                    "binance-"
                    + uuid5(
                        NAMESPACE_URL,
                        f"binance:{intent.account_id}:{self._symbol(intent)}:{trade['id']}",
                    ).hex,
                    client_order_id,
                    intent.instrument,
                    intent.side,
                    credited,
                    price,
                    fee,
                    quote,
                    datetime.fromtimestamp(int(trade["time"]) / 1000, tz=UTC),
                )
            )
        if (
            executed_by_trades != executed
            or executed > intent.quantity
            or quote_by_trades != _decimal(order.get("cummulativeQuoteQty"))
        ):
            raise BinancePrivateError("Incomplete trade evidence")
        return tuple(fills)

    async def cancel_order(self, client_order_id: str) -> CancelResult:
        try:
            found = await self._find(client_order_id)
            if found is None:
                return CancelResult(CancelOutcome.UNKNOWN, Decimal(0))
            intent, _ = found
            try:
                await self.transport.call(
                    "DELETE",
                    "/api/v3/order",
                    {"symbol": self._symbol(intent), "origClientOrderId": client_order_id},
                )
            except BinancePrivateError:
                pass  # Already terminal or unknown; the lookup below is authoritative.
            observed = await self.lookup_order(client_order_id)
            if observed.status is VenueOrderStatus.FILLED:
                return CancelResult(
                    CancelOutcome.FILL_WON_RACE, observed.cumulative_filled_quantity
                )
            if observed.status is VenueOrderStatus.CANCELLED:
                return CancelResult(CancelOutcome.CANCELLED, observed.cumulative_filled_quantity)
        except BinancePrivateError:
            pass
        return CancelResult(CancelOutcome.UNKNOWN, Decimal(0))
