from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from wallybot.domain.execution import CancelOutcome, SubmissionOutcome, VenueOrderStatus
from wallybot.domain.market import Instrument
from wallybot.domain.order import OrderIntent, OrderKind, Side
from wallybot.exchanges.fake import FakeExchange, ScriptedFill

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_intent(instrument: Instrument, **overrides: Any) -> OrderIntent:
    fields: dict[str, Any] = {
        "account_id": "acct-1",
        "environment": "PAPER",
        "instrument": instrument,
        "side": Side.BUY,
        "kind": OrderKind.MARKET,
        "quantity": instrument.min_quantity * 10,
        "limit_price": None,
        "decision_id": "decision-1",
        "client_order_id": "order-1",
        "idempotency_key": "order-1",
        "risk_assessment_id": "risk-1",
        "config_versions": {},
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=1),
    }
    fields.update(overrides)
    return OrderIntent(**fields)


async def gateway(**scripts: Any) -> tuple[FakeExchange, Instrument]:
    exchange = FakeExchange(
        clock=FixedClock(NOW),
        seed=1,
        balances={"USD": Decimal("1000000"), "BTC": Decimal("10")},
        **scripts,
    )
    instrument = (await exchange.discover_instruments())[0]
    return exchange, instrument


async def test_rejects_quantity_below_instrument_minimum() -> None:
    exchange, instrument = await gateway()
    intent = make_intent(instrument, quantity=instrument.min_quantity / 2)
    result = await exchange.submit_order(intent)
    assert result.outcome is SubmissionOutcome.REJECTED
    assert result.reason == "quantity below instrument minimum"
    lookup = await exchange.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.REJECTED


async def test_rejects_insufficient_balance() -> None:
    exchange = FakeExchange(clock=FixedClock(NOW), seed=1, balances={"USD": Decimal("1")})
    instrument = (await exchange.discover_instruments())[0]
    intent = make_intent(instrument)
    result = await exchange.submit_order(intent)
    assert result.outcome is SubmissionOutcome.REJECTED
    assert result.reason is not None and "insufficient" in result.reason


async def test_market_order_fills_fully_and_settles_balances() -> None:
    exchange, instrument = await gateway()
    starting_usd = exchange.balances["USD"]
    intent = make_intent(instrument)
    result = await exchange.submit_order(intent)
    assert result.outcome is SubmissionOutcome.ACCEPTED

    fills = await exchange.list_fills(intent.client_order_id)
    assert len(fills) == 1
    fill = fills[0]
    assert fill.quantity == intent.quantity
    assert fill.fee > 0

    lookup = await exchange.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.FILLED
    assert lookup.cumulative_filled_quantity == intent.quantity

    assert exchange.balances["BTC"] == Decimal(10) + intent.quantity
    assert exchange.balances["USD"] == starting_usd - fill.quantity * fill.price - fill.fee


async def test_unscripted_limit_order_does_not_fill() -> None:
    exchange, instrument = await gateway()
    intent = make_intent(instrument, kind=OrderKind.LIMIT, limit_price=Decimal("50000"))
    result = await exchange.submit_order(intent)
    assert result.outcome is SubmissionOutcome.ACCEPTED

    lookup = await exchange.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.ACKNOWLEDGED
    assert lookup.cumulative_filled_quantity == 0
    assert await exchange.list_fills(intent.client_order_id) == ()


async def test_scripted_partial_fills_accumulate_to_partially_filled_then_filled() -> None:
    _, instrument = await gateway()
    exchange, instrument = await gateway(
        fill_script={
            "order-1": [
                ScriptedFill(quantity=instrument.min_quantity * 4, price=Decimal("60000")),
                ScriptedFill(quantity=instrument.min_quantity * 6, price=Decimal("60010")),
            ]
        }
    )
    intent = make_intent(instrument, kind=OrderKind.LIMIT, limit_price=Decimal("60100"))
    await exchange.submit_order(intent)

    fills = await exchange.list_fills(intent.client_order_id)
    assert len(fills) == 2
    lookup = await exchange.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.FILLED
    assert lookup.cumulative_filled_quantity == intent.quantity
    expected_average = (
        fills[0].price * fills[0].quantity + fills[1].price * fills[1].quantity
    ) / intent.quantity
    assert lookup.average_fill_price == expected_average


async def test_scripted_partial_fill_leaves_order_partially_filled_for_cancel_race() -> None:
    _, instrument = await gateway()
    exchange, instrument = await gateway(
        fill_script={"order-1": [ScriptedFill(quantity=instrument.min_quantity * 3)]}
    )
    intent = make_intent(instrument, kind=OrderKind.LIMIT, limit_price=Decimal("60100"))
    await exchange.submit_order(intent)

    lookup = await exchange.lookup_order(intent.client_order_id)
    assert lookup.status is VenueOrderStatus.PARTIALLY_FILLED

    cancel = await exchange.cancel_order(intent.client_order_id)
    assert cancel.outcome is CancelOutcome.CANCELLED
    assert cancel.cumulative_filled_quantity == instrument.min_quantity * 3

    final_lookup = await exchange.lookup_order(intent.client_order_id)
    assert final_lookup.status is VenueOrderStatus.CANCELLED
    # Fills already posted before the cancellation observation are retained, never erased.
    assert final_lookup.cumulative_filled_quantity == instrument.min_quantity * 3


async def test_scripted_rejection() -> None:
    exchange, instrument = await gateway(submission_script={"order-1": SubmissionOutcome.REJECTED})
    intent = make_intent(instrument)
    result = await exchange.submit_order(intent)
    assert result.outcome is SubmissionOutcome.REJECTED
    assert await exchange.list_fills(intent.client_order_id) == ()


async def test_cancelling_an_already_filled_order_reports_zero_new_fills() -> None:
    exchange, instrument = await gateway()
    intent = make_intent(instrument)
    await exchange.submit_order(intent)
    cancel = await exchange.cancel_order(intent.client_order_id)
    assert cancel.outcome is CancelOutcome.FILL_WON_RACE
    second_cancel = await exchange.cancel_order(intent.client_order_id)
    assert second_cancel.outcome is CancelOutcome.FILL_WON_RACE


async def test_cancelling_unknown_order_id_is_a_safe_no_op() -> None:
    exchange, _ = await gateway()
    cancel = await exchange.cancel_order("never-submitted")
    assert cancel.outcome is CancelOutcome.REJECTED_ZERO_FILLS
    assert cancel.cumulative_filled_quantity == 0


async def test_looking_up_unknown_order_id_returns_not_found() -> None:
    exchange, _ = await gateway()
    lookup = await exchange.lookup_order("never-submitted")
    assert lookup.status is VenueOrderStatus.NOT_FOUND
