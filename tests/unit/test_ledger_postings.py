from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.application.ledger_postings import build_fill_ledger_transaction
from wallybot.domain.execution import Fill
from wallybot.domain.ledger import AccountPurpose
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import Side

NOW = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


def make_fill(**overrides: Any) -> Fill:
    fields: dict[str, Any] = {
        "fill_id": "fill-1",
        "client_order_id": "order-1",
        "instrument": INSTRUMENT,
        "side": Side.BUY,
        "quantity": Decimal("1"),
        "price": Decimal("60000"),
        "fee": Decimal("6"),
        "fee_currency": "USD",
        "filled_at": NOW,
    }
    fields.update(overrides)
    return Fill(**fields)


def test_a_buy_fill_produces_a_balanced_four_leg_transaction() -> None:
    fill = make_fill(side=Side.BUY)
    transaction = build_fill_ledger_transaction(fill, account_id="acct-1")

    assert transaction.reference_id == fill.fill_id
    assert len(transaction.postings) == 4

    totals: dict[str, Decimal] = {}
    for posting in transaction.postings:
        totals[posting.account.currency] = (
            totals.get(posting.account.currency, Decimal(0)) + posting.amount
        )
    assert all(total == 0 for total in totals.values())

    cash_leg = next(
        p
        for p in transaction.postings
        if p.account.account_id == "acct-1" and p.account.purpose == AccountPurpose.CASH
    )
    assert cash_leg.amount == -(fill.quantity * fill.price + fill.fee)

    position_leg = next(
        p
        for p in transaction.postings
        if p.account.account_id == "acct-1" and p.account.purpose == AccountPurpose.POSITION
    )
    assert position_leg.amount == fill.quantity


def test_a_sell_fill_credits_cash_net_of_fee_and_debits_the_position() -> None:
    fill = make_fill(
        side=Side.SELL, quantity=Decimal("0.5"), price=Decimal("60000"), fee=Decimal("3")
    )
    transaction = build_fill_ledger_transaction(fill, account_id="acct-1")

    cash_leg = next(
        p
        for p in transaction.postings
        if p.account.account_id == "acct-1" and p.account.purpose == AccountPurpose.CASH
    )
    assert cash_leg.amount == fill.quantity * fill.price - fill.fee

    position_leg = next(
        p
        for p in transaction.postings
        if p.account.account_id == "acct-1" and p.account.purpose == AccountPurpose.POSITION
    )
    assert position_leg.amount == -fill.quantity

    totals: dict[str, Decimal] = {}
    for posting in transaction.postings:
        totals[posting.account.currency] = (
            totals.get(posting.account.currency, Decimal(0)) + posting.amount
        )
    assert all(total == 0 for total in totals.values())


def test_a_non_quote_fee_currency_is_rejected_rather_than_silently_mis_booked() -> None:
    fill = make_fill(fee_currency="BTC")
    with pytest.raises(ValueError, match="fee currency"):
        build_fill_ledger_transaction(fill, account_id="acct-1")
