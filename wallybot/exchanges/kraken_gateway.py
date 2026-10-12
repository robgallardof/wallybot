"""Spot order gateway with durable intent identities and reconcile-before-retry semantics."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

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
from wallybot.exchanges.kraken_private import (
    KrakenPrivateError,
    PrivateTransport,
    validate_permissions,
)


class KrakenSpotGateway:
    def __init__(
        self,
        transport: PrivateTransport,
        load_intent: Callable[[str], Awaitable[OrderIntent]],
        now: Callable[[], datetime],
        authorize: Callable[[OrderIntent], Awaitable[bool]] | None = None,
    ) -> None:
        self.transport = transport
        self.load_intent = load_intent
        self.now = now
        self.authorize = authorize

    async def submit_order(self, intent: OrderIntent) -> SubmissionResult:
        if (
            intent.environment != "LIVE"
            or intent.instrument.venue != "kraken"
            or intent.instrument.market_type != MarketType.SPOT
        ):
            return SubmissionResult(
                SubmissionOutcome.REJECTED, reason="Only LIVE Kraken spot intents are supported"
            )
        if intent.expires_at <= self.now():
            return SubmissionResult(SubmissionOutcome.REJECTED, reason="Intent expired")
        try:
            UUID(intent.client_order_id)
            validate_permissions(await self.transport.call("GetApiKeyInfo", {}))
        except (ValueError, KrakenPrivateError):
            return SubmissionResult(
                SubmissionOutcome.REJECTED, reason="Invalid identity or key permissions"
            )
        params = {
            "pair": intent.instrument.base + intent.instrument.quote,
            "type": intent.side.value.lower(),
            "ordertype": intent.kind.value.lower(),
            "volume": format(intent.quantity, "f"),
            "cl_ord_id": intent.client_order_id,
            "oflags": "fciq",
        }
        if intent.kind is OrderKind.LIMIT:
            params["price"] = format(intent.limit_price, "f")
            params["timeinforce"] = "IOC"
        try:
            if intent.expires_at <= self.now() or (
                self.authorize is not None and not await self.authorize(intent)
            ):
                return SubmissionResult(
                    SubmissionOutcome.REJECTED, reason="Execution authorization changed"
                )
            result = await self.transport.call("AddOrder", params)
            ids = result.get("txid")
            if (
                not isinstance(ids, list)
                or len(ids) != 1
                or not isinstance(ids[0], str)
                or not ids[0]
            ):
                raise KrakenPrivateError("Invalid order response")
            return SubmissionResult(SubmissionOutcome.ACCEPTED, venue_order_id=ids[0])
        except KrakenPrivateError:
            # A provider error can follow acceptance. No retry, even for apparent rejection.
            return SubmissionResult(
                SubmissionOutcome.UNKNOWN, reason="Submission requires reconciliation"
            )

    async def _find(self, client_order_id: str) -> tuple[str, dict[str, Any]] | None:
        intent = await self.load_intent(client_order_id)
        if intent.environment != "LIVE" or intent.instrument.venue != "kraken":
            raise KrakenPrivateError("Order scope mismatch")
        opened = await self.transport.call(
            "OpenOrders", {"trades": "true", "cl_ord_id": client_order_id}
        )
        candidates = [
            (key, row)
            for key, row in opened["open"].items()
            if row.get("cl_ord_id") == client_order_id or "cl_ord_id" not in row
        ]
        offset = 0
        # Scan closed history since the durable intent, not merely the last 50 orders.
        for _ in range(100):
            closed = await self.transport.call(
                "ClosedOrders",
                {
                    "trades": "true",
                    "cl_ord_id": client_order_id,
                    "start": str(int(intent.created_at.timestamp()) - 60),
                    "ofs": str(offset),
                },
            )
            rows = closed["closed"]
            candidates.extend(
                (key, row)
                for key, row in rows.items()
                if row.get("cl_ord_id") == client_order_id or "cl_ord_id" not in row
            )
            offset += len(rows)
            if offset >= int(closed["count"]):
                break
            if not rows:
                raise KrakenPrivateError("Incomplete order history")
        else:
            raise KrakenPrivateError("Order history exceeds reconciliation limit")
        # An order can close between the two queries; collapse that same venue identity.
        unique = dict(candidates)
        if len(unique) > 1:
            raise KrakenPrivateError("Duplicate client order identity")
        if not unique:
            return None
        venue_id, row = next(iter(unique.items()))
        descr = row["descr"]
        if (
            descr["pair"].replace("/", "") != intent.instrument.base + intent.instrument.quote
            or descr["type"] != intent.side.value.lower()
            or Decimal(str(row["vol"])) != intent.quantity
        ):
            raise KrakenPrivateError("Exchange order differs from approved intent")
        return venue_id, row

    async def lookup_order(self, client_order_id: str) -> OrderLookup:
        found = await self._find(client_order_id)
        if found is None:
            return OrderLookup(VenueOrderStatus.NOT_FOUND, Decimal(0), None)
        venue_id, row = found
        quantity = Decimal(str(row["vol_exec"]))
        status = row["status"]
        if status in {"canceled", "expired"}:
            state = VenueOrderStatus.CANCELLED
        elif status == "closed":
            state = (
                VenueOrderStatus.FILLED
                if quantity == Decimal(str(row["vol"]))
                else VenueOrderStatus.CANCELLED
            )
        elif status in {"pending", "open"}:
            state = VenueOrderStatus.PARTIALLY_FILLED if quantity else VenueOrderStatus.ACKNOWLEDGED
        else:
            raise KrakenPrivateError("Unknown exchange order status")
        return OrderLookup(
            state, quantity, Decimal(str(row["price"])) if quantity else None, venue_id
        )

    async def list_fills(self, client_order_id: str) -> tuple[Fill, ...]:
        found = await self._find(client_order_id)
        if found is None:
            return ()
        venue_id, order = found
        trade_ids = order.get("trades", [])
        if not trade_ids:
            if Decimal(str(order["vol_exec"])):
                raise KrakenPrivateError("Executed volume has no trade evidence")
            return ()
        intent = await self.load_intent(client_order_id)
        fills = []
        for offset in range(0, len(trade_ids), 20):
            trades = await self.transport.call(
                "QueryTrades", {"txid": ",".join(trade_ids[offset : offset + 20])}
            )
            for trade_id in trade_ids[offset : offset + 20]:
                trade = trades[trade_id]
                if (
                    trade["ordertxid"] != venue_id
                    or trade["type"] != intent.side.value.lower()
                    or Decimal(str(trade.get("margin", "0")))
                ):
                    raise KrakenPrivateError("Trade evidence scope mismatch")
                fills.append(
                    Fill(
                        trade_id,
                        client_order_id,
                        intent.instrument,
                        Side(trade["type"].upper()),
                        Decimal(str(trade["vol"])),
                        Decimal(str(trade["cost"])) / Decimal(str(trade["vol"]))
                        if "cost" in trade
                        else Decimal(str(trade["price"])),
                        Decimal(str(trade["fee"])),
                        intent.instrument.quote,
                        datetime(1970, 1, 1, tzinfo=UTC)
                        + timedelta(microseconds=int(Decimal(str(trade["time"])) * 1_000_000)),
                    )
                )
        if sum((fill.quantity for fill in fills), Decimal(0)) != Decimal(str(order["vol_exec"])):
            raise KrakenPrivateError("Incomplete trade evidence")
        return tuple(fills)

    async def cancel_order(self, client_order_id: str) -> CancelResult:
        try:
            found = await self._find(client_order_id)
            if found is None:
                return CancelResult(CancelOutcome.UNKNOWN, Decimal(0))
            venue_id, _ = found
            await self.transport.call("CancelOrder", {"txid": venue_id})
            observed = await self.lookup_order(client_order_id)
            if observed.status is VenueOrderStatus.FILLED:
                return CancelResult(
                    CancelOutcome.FILL_WON_RACE, observed.cumulative_filled_quantity
                )
            if observed.status is VenueOrderStatus.CANCELLED:
                return CancelResult(CancelOutcome.CANCELLED, observed.cumulative_filled_quantity)
        except KrakenPrivateError:
            pass
        return CancelResult(CancelOutcome.UNKNOWN, Decimal(0))
