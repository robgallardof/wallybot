"""Scripted Binance spot account with the documented private-API semantics. Never a funded key."""

from datetime import UTC, datetime
from decimal import Decimal

from wallybot.exchanges.binance_private import BinanceOrderNotFound, BinancePrivateError

SAFE_RESTRICTIONS = {
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
    "enableFixReadOnly": False,
    "enableSpotAndMarginTrading": True,
    "enablePortfolioMarginTrading": False,
}


class FakeBinanceAccount:
    def __init__(self) -> None:
        self.balances = {"USDT": Decimal("1000")}
        self.orders: dict[str, dict] = {}
        self.trades: dict[int, list[dict]] = {}
        self.calls: list[tuple[str, str, dict]] = []
        self.restrictions = dict(SAFE_RESTRICTIONS)
        self.external_open = False
        self.timeout = False
        self.fee_asset: str | None = None  # None: Binance default (base on BUY, quote on SELL)
        self.fill_ratio = Decimal(1)

    async def call(self, method: str, path: str, params: dict[str, str]):
        self.calls.append((method, path, params.copy()))
        if path == "/sapi/v1/account/apiRestrictions":
            return dict(self.restrictions)
        if path == "/api/v3/account":
            return {
                "accountType": "SPOT",
                "canTrade": True,
                "balances": [
                    {"asset": asset, "free": str(total), "locked": "0"}
                    for asset, total in self.balances.items()
                ],
            }
        if path == "/api/v3/openOrders":
            return [{"symbol": "BTCUSDT", "orderId": 99}] if self.external_open else []
        if path == "/api/v3/account/commission":
            zero = {"maker": "0", "taker": "0", "buyer": "0", "seller": "0"}
            return {
                "symbol": params["symbol"],
                "standardCommission": {**zero, "maker": "0.001", "taker": "0.001"},
                "specialCommission": zero,
                "taxCommission": zero,
            }
        if path == "/api/v3/order" and method == "POST":
            return self._place(params)
        if path == "/api/v3/order" and method == "GET":
            order = self.orders.get(params["origClientOrderId"])
            if order is None:
                raise BinanceOrderNotFound("Binance has no order with this identity")
            return dict(order)
        if path == "/api/v3/order" and method == "DELETE":
            raise BinancePrivateError("Binance rejected the private request")
        if path == "/api/v3/myTrades":
            return list(self.trades.get(int(params["orderId"]), []))
        raise AssertionError((method, path))

    def _place(self, params: dict[str, str]) -> dict:
        assert params["type"] == "LIMIT" and params["timeInForce"] == "IOC"
        base = params["symbol"].removesuffix("USDT")
        quantity, price = Decimal(params["quantity"]), Decimal(params["price"])
        executed = quantity * self.fill_ratio
        order_id = len(self.orders) + 1
        buy = params["side"] == "BUY"
        cost = executed * price
        if buy:
            asset = self.fee_asset or base
            fee = executed * Decimal("0.001") if asset == base else cost * Decimal("0.001")
            self.balances["USDT"] -= cost
            self.balances[base] = self.balances.get(base, Decimal(0)) + executed
        else:
            asset = self.fee_asset or "USDT"
            fee = cost * Decimal("0.001")
            self.balances["USDT"] += cost
            self.balances[base] -= executed
        self.balances[asset] = self.balances.get(asset, Decimal(0)) - fee
        self.orders[params["newClientOrderId"]] = {
            "symbol": params["symbol"],
            "orderId": order_id,
            "clientOrderId": params["newClientOrderId"],
            "price": params["price"],
            "origQty": params["quantity"],
            "executedQty": str(executed),
            "cummulativeQuoteQty": str(cost),
            "status": "FILLED" if executed == quantity else "EXPIRED",
            "timeInForce": "IOC",
            "type": "LIMIT",
            "side": params["side"],
        }
        self.trades[order_id] = (
            [
                {
                    "symbol": params["symbol"],
                    "id": 1000 + order_id,
                    "orderId": order_id,
                    "price": str(price),
                    "qty": str(executed),
                    "quoteQty": str(cost),
                    "commission": str(fee),
                    "commissionAsset": asset,
                    "time": int(datetime.now(UTC).timestamp() * 1000),
                    "isBuyer": buy,
                }
            ]
            if executed
            else []
        )
        if self.timeout:
            raise BinancePrivateError("accepted but response lost")
        return {
            "symbol": params["symbol"],
            "orderId": order_id,
            "clientOrderId": params["newClientOrderId"],
        }
