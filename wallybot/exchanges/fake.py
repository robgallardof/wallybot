import random
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from wallybot.domain.clock import Clock
from wallybot.domain.execution import (
    CancelOutcome,
    CancelResult,
    Fill,
    OrderLookup,
    SubmissionOutcome,
    SubmissionResult,
    VenueOrderStatus,
)
from wallybot.domain.market import (
    TIMEFRAME_DURATIONS,
    Candle,
    Instrument,
    MarketSnapshot,
    MarketType,
)
from wallybot.domain.order import OrderIntent, OrderKind, Side


def _require_precision(instrument: Instrument) -> tuple[Decimal, Decimal, Decimal]:
    """Narrow an Instrument's optional precision fields to real values or fail closed.

    FakeExchange simulates real order execution, which is meaningless without a real tick/lot
    size -- unlike a display-only path, there is no honest way to proceed with "unknown"
    precision here. Every Instrument this simulator actually deals with (its own seeded fixtures)
    always has real precision; this only guards against a caller passing in one that doesn't.
    """
    price_increment, quantity_increment, min_quantity = (
        instrument.price_increment,
        instrument.quantity_increment,
        instrument.min_quantity,
    )
    if price_increment is None or quantity_increment is None or min_quantity is None:
        raise ValueError(f"{instrument.id} has no reported precision; cannot simulate execution")
    return price_increment, quantity_increment, min_quantity


@dataclass(frozen=True)
class ScriptedFill:
    """One fill to post for a scripted order. `price=None` uses the current reference quote,
    same as an unscripted market fill would."""

    quantity: Decimal
    price: Decimal | None = None


@dataclass(frozen=True)
class _SimulatedOrder:
    instrument: Instrument
    side: Side
    quantity: Decimal
    status: VenueOrderStatus
    venue_order_id: str | None
    cumulative_filled_quantity: Decimal
    average_fill_price: Decimal | None


class FakeExchange:
    """Seeded, network-free MarketDataProvider and ExchangeGateway for deterministic tests and
    local dev -- the "seeded FakeExchange" TESTING.md requires for the paper pipeline.

    Fills happen synchronously inside `submit_order`: an unscripted MARKET order fills fully at
    the current reference quote; an unscripted LIMIT order does not fill at all (there is no
    matching engine here -- that belongs to backtesting/Phase 5, not this simulator). Tests drive
    partial fills, rejections and "accept-then-timeout" ambiguity with `submission_script`,
    `cancel_script` and `fill_script`, keyed by `client_order_id` per TESTING.md's "Inject a clock
    and scripted outcomes."
    """

    def __init__(
        self,
        clock: Clock,
        seed: int = 0,
        balances: dict[str, Decimal] | None = None,
        fee_rate: Decimal = Decimal("0.001"),
        submission_script: dict[str, SubmissionOutcome] | None = None,
        cancel_script: dict[str, CancelOutcome] | None = None,
        fill_script: dict[str, list[ScriptedFill]] | None = None,
    ) -> None:
        self.clock = clock
        self.seed = seed
        self.balances: dict[str, Decimal] = dict(balances or {})
        self.fee_rate = fee_rate
        self._submission_script = dict(submission_script or {})
        self._cancel_script = dict(cancel_script or {})
        self._fill_script = {key: list(value) for key, value in (fill_script or {}).items()}
        self._orders: dict[str, _SimulatedOrder] = {}
        self._fills: dict[str, list[Fill]] = {}
        self._fill_counter = 0
        self._instruments = [
            Instrument(
                venue="fake",
                market_type=MarketType.SPOT,
                base="BTC",
                quote="USD",
                price_increment=Decimal("0.01"),
                quantity_increment=Decimal("0.0001"),
                min_quantity=Decimal("0.0001"),
            ),
            Instrument(
                venue="fake",
                market_type=MarketType.SPOT,
                base="ETH",
                quote="USD",
                price_increment=Decimal("0.01"),
                quantity_increment=Decimal("0.001"),
                min_quantity=Decimal("0.001"),
            ),
        ]
        self._base_price = {"BTC/USD": Decimal("60000"), "ETH/USD": Decimal("3000")}

    async def discover_instruments(self) -> list[Instrument]:
        return list(self._instruments)

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        if timeframe not in TIMEFRAME_DURATIONS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        price_increment, quantity_increment, _min_quantity = _require_precision(instrument)
        step = TIMEFRAME_DURATIONS[timeframe]
        pair = f"{instrument.base}/{instrument.quote}"
        base_price = self._base_price.get(pair, Decimal("100"))
        now = self.clock.now()
        rng = random.Random(f"{self.seed}:{instrument.id}:{timeframe}:{since.isoformat()}")
        candles: list[Candle] = []
        price = base_price
        open_time = since
        while len(candles) < limit and open_time + step <= now:
            close_time = open_time + step
            drift = Decimal(rng.uniform(-0.01, 0.01)) * price
            close_price = max(price + drift, price_increment)
            wick = Decimal(rng.uniform(0, 0.005)) * price
            high = max(price, close_price) + wick
            low = max(min(price, close_price) - wick, price_increment)
            volume = Decimal(rng.uniform(0.1, 10)).quantize(quantity_increment)
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=price.quantize(price_increment),
                    high=high.quantize(price_increment),
                    low=low.quantize(price_increment),
                    close=close_price.quantize(price_increment),
                    volume=volume,
                    source="fake",
                    received_at=now,
                )
            )
            price = close_price
            open_time = close_time
        return candles

    def _quote(self, instrument: Instrument) -> tuple[Decimal, Decimal]:
        price_increment, _quantity_increment, _min_quantity = _require_precision(instrument)
        pair = f"{instrument.base}/{instrument.quote}"
        mid = self._base_price.get(pair, Decimal("100"))
        rng = random.Random(f"{self.seed}:{instrument.id}:snapshot:{self.clock.now().isoformat()}")
        half_spread = mid * Decimal(rng.uniform(0.0001, 0.0015))
        return (
            (mid - half_spread).quantize(price_increment),
            (mid + half_spread).quantize(price_increment),
        )

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        bid, ask = self._quote(instrument)
        return MarketSnapshot(
            instrument=instrument, bid=bid, ask=ask, timestamp=self.clock.now(), source="fake"
        )

    def _reference_price(self, instrument: Instrument, side: Side) -> Decimal:
        bid, ask = self._quote(instrument)
        return ask if side is Side.BUY else bid

    def _validate(self, intent: OrderIntent) -> str | None:
        _price_increment, _quantity_increment, min_quantity = _require_precision(
            intent.instrument
        )
        if intent.quantity < min_quantity:
            return "quantity below instrument minimum"
        price = (
            intent.limit_price
            if intent.kind is OrderKind.LIMIT
            else self._reference_price(intent.instrument, intent.side)
        )
        assert price is not None
        if intent.side is Side.BUY:
            currency, required = intent.instrument.quote, intent.quantity * price
        else:
            currency, required = intent.instrument.base, intent.quantity
        if self.balances.get(currency, Decimal(0)) < required:
            return f"insufficient {currency} balance"
        return None

    def _settle(self, intent: OrderIntent, quantity: Decimal, price: Decimal, fee: Decimal) -> None:
        base, quote = intent.instrument.base, intent.instrument.quote
        if intent.side is Side.BUY:
            self.balances[quote] = self.balances.get(quote, Decimal(0)) - quantity * price - fee
            self.balances[base] = self.balances.get(base, Decimal(0)) + quantity
        else:
            self.balances[base] = self.balances.get(base, Decimal(0)) - quantity
            self.balances[quote] = self.balances.get(quote, Decimal(0)) + quantity * price - fee

    def _post_fill(self, intent: OrderIntent, quantity: Decimal, price: Decimal) -> None:
        order = self._orders[intent.client_order_id]
        if order.status in (
            VenueOrderStatus.FILLED,
            VenueOrderStatus.CANCELLED,
            VenueOrderStatus.REJECTED,
        ):
            return
        self._fill_counter += 1
        price_increment, _quantity_increment, _min_quantity = _require_precision(
            intent.instrument
        )
        fee = (quantity * price * self.fee_rate).quantize(price_increment)
        fill = Fill(
            fill_id=f"fake-fill-{self._fill_counter}",
            client_order_id=intent.client_order_id,
            instrument=intent.instrument,
            side=intent.side,
            quantity=quantity,
            price=price,
            fee=fee,
            fee_currency=intent.instrument.quote,
            filled_at=self.clock.now(),
        )
        self._fills[intent.client_order_id].append(fill)
        self._settle(intent, quantity, price, fee)
        previous_notional = (
            order.average_fill_price or Decimal(0)
        ) * order.cumulative_filled_quantity
        new_cumulative = order.cumulative_filled_quantity + quantity
        new_average = (previous_notional + price * quantity) / new_cumulative
        new_status = (
            VenueOrderStatus.FILLED
            if new_cumulative >= order.quantity
            else VenueOrderStatus.PARTIALLY_FILLED
        )
        self._orders[intent.client_order_id] = replace(
            order,
            cumulative_filled_quantity=new_cumulative,
            average_fill_price=new_average,
            status=new_status,
        )

    def _apply_scripted_or_default_fills(self, intent: OrderIntent) -> None:
        plan = self._fill_script.get(intent.client_order_id)
        if plan is None:
            plan = (
                [ScriptedFill(quantity=intent.quantity)] if intent.kind is OrderKind.MARKET else []
            )
        for scripted in plan:
            price = (
                scripted.price
                if scripted.price is not None
                else self._reference_price(intent.instrument, intent.side)
            )
            self._post_fill(intent, scripted.quantity, price)

    async def submit_order(self, intent: OrderIntent) -> SubmissionResult:
        rejection_reason = self._validate(intent)
        if rejection_reason is not None:
            self._orders[intent.client_order_id] = _SimulatedOrder(
                instrument=intent.instrument,
                side=intent.side,
                quantity=intent.quantity,
                status=VenueOrderStatus.REJECTED,
                venue_order_id=None,
                cumulative_filled_quantity=Decimal(0),
                average_fill_price=None,
            )
            self._fills.setdefault(intent.client_order_id, [])
            return SubmissionResult(SubmissionOutcome.REJECTED, reason=rejection_reason)

        scripted_outcome = self._submission_script.get(intent.client_order_id)
        if scripted_outcome is SubmissionOutcome.REJECTED:
            self._orders[intent.client_order_id] = _SimulatedOrder(
                instrument=intent.instrument,
                side=intent.side,
                quantity=intent.quantity,
                status=VenueOrderStatus.REJECTED,
                venue_order_id=None,
                cumulative_filled_quantity=Decimal(0),
                average_fill_price=None,
            )
            self._fills.setdefault(intent.client_order_id, [])
            return SubmissionResult(SubmissionOutcome.REJECTED, reason="scripted rejection")

        venue_order_id = f"fake-{intent.client_order_id}"
        self._orders[intent.client_order_id] = _SimulatedOrder(
            instrument=intent.instrument,
            side=intent.side,
            quantity=intent.quantity,
            status=VenueOrderStatus.ACKNOWLEDGED,
            venue_order_id=venue_order_id,
            cumulative_filled_quantity=Decimal(0),
            average_fill_price=None,
        )
        self._fills.setdefault(intent.client_order_id, [])
        self._apply_scripted_or_default_fills(intent)

        if scripted_outcome is SubmissionOutcome.UNKNOWN:
            # The order really was accepted at the venue; only the response telling the caller
            # so was lost. lookup_order (keyed by client_order_id, never a venue-assigned ID that
            # was never received) still resolves it -- ADR-008's reconcile-before-retry.
            return SubmissionResult(
                SubmissionOutcome.UNKNOWN, reason="response lost after acceptance"
            )
        return SubmissionResult(SubmissionOutcome.ACCEPTED, venue_order_id=venue_order_id)

    async def cancel_order(self, client_order_id: str) -> CancelResult:
        order = self._orders.get(client_order_id)
        if order is None:
            return CancelResult(
                CancelOutcome.REJECTED_ZERO_FILLS, cumulative_filled_quantity=Decimal(0)
            )
        if self._cancel_script.get(client_order_id) is CancelOutcome.UNKNOWN:
            return CancelResult(
                CancelOutcome.UNKNOWN, cumulative_filled_quantity=order.cumulative_filled_quantity
            )
        if order.status is VenueOrderStatus.FILLED:
            return CancelResult(
                CancelOutcome.FILL_WON_RACE,
                cumulative_filled_quantity=order.cumulative_filled_quantity,
            )
        if order.status in (VenueOrderStatus.CANCELLED, VenueOrderStatus.REJECTED):
            return CancelResult(
                CancelOutcome.REJECTED_ZERO_FILLS,
                cumulative_filled_quantity=order.cumulative_filled_quantity,
            )
        self._orders[client_order_id] = replace(order, status=VenueOrderStatus.CANCELLED)
        return CancelResult(
            CancelOutcome.CANCELLED, cumulative_filled_quantity=order.cumulative_filled_quantity
        )

    async def lookup_order(self, client_order_id: str) -> OrderLookup:
        order = self._orders.get(client_order_id)
        if order is None:
            return OrderLookup(
                VenueOrderStatus.NOT_FOUND,
                cumulative_filled_quantity=Decimal(0),
                average_fill_price=None,
            )
        return OrderLookup(
            order.status,
            order.cumulative_filled_quantity,
            order.average_fill_price,
            order.venue_order_id,
        )

    async def list_fills(self, client_order_id: str) -> tuple[Fill, ...]:
        return tuple(self._fills.get(client_order_id, ()))
