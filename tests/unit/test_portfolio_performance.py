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
