from dataclasses import dataclass
from decimal import Decimal

import pytest

from wallybot.application.portfolio_performance import compute_fifo_performance


@dataclass(frozen=True)
class Fill:
    base: str
    quote: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str = "USD"


def test_fifo_performance_reports_realized_result_and_open_cost() -> None:
    result = compute_fifo_performance(
        [
            Fill("BTC", "USD", "BUY", Decimal("1"), Decimal("100"), Decimal("1")),
            Fill("BTC", "USD", "BUY", Decimal("1"), Decimal("200"), Decimal("2")),
            Fill("BTC", "USD", "SELL", Decimal("1.5"), Decimal("300"), Decimal("3")),
        ]
    )

    assert result[0].quote == "USD"
    assert result[0].realized_pnl == Decimal("245")
    assert result[0].open_cost_basis == Decimal("101")


def test_fifo_performance_rejects_a_sale_without_a_position() -> None:
    with pytest.raises(ValueError, match="exceeds"):
        compute_fifo_performance(
            [Fill("BTC", "USD", "SELL", Decimal("1"), Decimal("100"), Decimal("1"))]
        )


def test_open_positions_keep_fifo_average_and_oldest_open_buy() -> None:
    from datetime import UTC, datetime

    from wallybot.application.portfolio_performance import open_positions

    @dataclass(frozen=True)
    class TimedFill:
        base: str
        side: str
        quantity: Decimal
        price: Decimal
        filled_at: datetime

    day = lambda d: datetime(2026, 10, d, tzinfo=UTC)  # noqa: E731
    result = open_positions(
        [
            TimedFill("DOT", "BUY", Decimal("2"), Decimal("4"), day(1)),
            TimedFill("DOT", "BUY", Decimal("2"), Decimal("6"), day(3)),
            TimedFill("DOT", "SELL", Decimal("3"), Decimal("7"), day(4)),
            TimedFill("UNI", "BUY", Decimal("1"), Decimal("8"), day(2)),
            TimedFill("UNI", "SELL", Decimal("1"), Decimal("9"), day(5)),
            # Selling coins the bot never bought (pre-existing balance) is not an error.
            TimedFill("XRP", "SELL", Decimal("1"), Decimal("2"), day(5)),
        ]
    )

    assert set(result) == {"DOT"}
    assert result["DOT"].quantity == Decimal("1")
    assert result["DOT"].average_price == Decimal("6")
    assert result["DOT"].held_since == day(3)
