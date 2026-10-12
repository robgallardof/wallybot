from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.application.position_monitoring import (
    attribute_fifo_positions,
    fetch_position_marks,
    level_status,
    trustworthy_mark,
)
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.infrastructure.models import FillRow

NOW = datetime(2026, 10, 8, tzinfo=UTC)
INSTRUMENT = Instrument("kraken", MarketType.SPOT, "BTC", "USD")


def fill(identifier, side, quantity, price, fee="0", at=NOW):
    return FillRow(
        fill_id=identifier,
        venue="kraken",
        base="BTC",
        quote="USD",
        side=side,
        quantity=Decimal(quantity),
        price=Decimal(price),
        fee=Decimal(fee),
        fee_currency="USD",
        filled_at=at,
    )


def test_partial_fifo_closures_preserve_cost_fees_and_attribution():
    history = [
        fill("first", "BUY", "1", "100", "1"),
        fill("second", "BUY", "1", "200", "2"),
        fill("sale", "SELL", "1.5", "300", "3", NOW + timedelta(hours=1)),
    ]
    result = attribute_fifo_positions(history)
    assert result["first"].remaining_quantity == 0
    assert result["first"].realized_pnl == Decimal("197")
    assert result["first"].closed_at == NOW + timedelta(hours=1)
    assert result["second"].remaining_quantity == Decimal("0.5")
    assert result["second"].remaining_cost == Decimal("101")
    assert result["second"].realized_pnl == Decimal("48")
    assert result["second"].closed_at is None
    assert result["sale"].realized_pnl == Decimal("245")
    history.append(fill("final", "SELL", "0.5", "150", "0.5", NOW + timedelta(days=1)))
    result = attribute_fifo_positions(history)
    assert result["second"].remaining_quantity == 0
    assert result["second"].remaining_cost == 0
    assert result["second"].realized_pnl == Decimal("21.5")
    assert result["second"].closed_at == NOW + timedelta(days=1)


@pytest.mark.parametrize(
    "history",
    [
        [fill("sell", "SELL", "1", "100")],
        [fill("same", "BUY", "1", "100"), fill("same", "BUY", "1", "100")],
        [fill("zero", "BUY", "0", "100")],
        [fill("bad", "BUY", "1", "NaN")],
        [fill("side", "SHORT", "1", "100")],
    ],
)
def test_invalid_or_incomplete_history_is_never_presented_as_profit(history):
    with pytest.raises(ValueError):
        attribute_fifo_positions(history)


def test_non_quote_fee_is_rejected_without_fabricating_conversion():
    item = fill("buy", "BUY", "1", "100")
    item.fee_currency = "BTC"
    with pytest.raises(ValueError, match="quote-currency"):
        attribute_fifo_positions([item])


@pytest.mark.parametrize(
    "age,bid,ask,valid",
    [
        (0, "100", "101", True),
        (60, "100", "101", True),
        (61, "100", "101", False),
        (-1, "100", "101", False),
        (0, "90", "100", False),
    ],
)
def test_marks_require_recent_nonfuture_quotes_and_bounded_spread(age, bid, ask, valid):
    snapshot = MarketSnapshot(
        INSTRUMENT, Decimal(bid), Decimal(ask), NOW - timedelta(seconds=age), "kraken"
    )
    assert trustworthy_mark(snapshot, INSTRUMENT, NOW) is valid
    other = Instrument("other", MarketType.SPOT, "BTC", "USD")
    assert not trustworthy_mark(snapshot, other, NOW)


@pytest.mark.parametrize(
    "remaining,price,expected",
    [
        ("0", None, "CLOSED"),
        ("1", None, "QUOTE_UNAVAILABLE"),
        ("1", "90", "STOP_REACHED"),
        ("1", "110", "TARGET_REACHED"),
        ("1", "100", "MONITORING"),
    ],
)
def test_followup_is_a_read_only_level_classification(remaining, price, expected):
    assert (
        level_status(
            Decimal(remaining), Decimal(price) if price else None, Decimal("90"), Decimal("110")
        )
        == expected
    )


async def test_quote_failure_does_not_hide_the_ledger_and_duplicate_pairs_fetch_once():
    class Provider:
        calls = 0

        async def fetch_snapshot(self, instrument):
            self.calls += 1
            raise RuntimeError("provider unavailable")

    provider = Provider()
    items = [fill("a", "BUY", "1", "100"), fill("b", "BUY", "1", "100")]
    assert await fetch_position_marks(provider, items) == {}
    assert provider.calls == 1
    assert await fetch_position_marks(None, items) == {}
