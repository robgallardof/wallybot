"""Deterministic FIFO cost-basis accounting for a PAPER fill history.

The portfolio page may report realised results and remaining cost basis, but never invents an
unrealised value when no trustworthy current quote is available.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from wallybot.infrastructure.models import FillRow

# A structural Protocol here would be nicer for testability, but SQLAlchemy 2's `Mapped[str]`
# column attributes don't structurally satisfy a Protocol under pyright (the class-level
# descriptor type, not the resolved instance type, is what gets checked) -- accepting the
# concrete `FillRow` directly avoids fighting that mismatch. Tests pass plain dataclasses with the
# same shape; that's fine at runtime (duck typing), pyright just never checks the test file
# against this signature.


@dataclass
class _Lot:
    quantity: Decimal
    cost: Decimal


@dataclass(frozen=True)
class QuotePerformance:
    quote: str
    realized_pnl: Decimal
    open_cost_basis: Decimal


def compute_fifo_performance(fills: Iterable[FillRow]) -> tuple[QuotePerformance, ...]:
    """Compute realised PnL and remaining FIFO cost basis per quote currency.

    Fills must be supplied oldest first.  A sale without a matching long lot is rejected: showing
    a partial made-up PnL would hide a ledger/position integrity problem.
    """
    lots: dict[tuple[str, str], list[_Lot]] = defaultdict(list)
    realized: dict[str, Decimal] = defaultdict(Decimal)

    for fill in fills:
        if fill.fee_currency != fill.quote:
            raise ValueError("FIFO performance requires fees in the quote currency")
        key = (fill.base, fill.quote)
        notional = fill.quantity * fill.price
        if fill.side == "BUY":
            lots[key].append(_Lot(quantity=fill.quantity, cost=notional + fill.fee))
            continue
        if fill.side != "SELL":
            raise ValueError(f"unsupported fill side: {fill.side}")

        remaining = fill.quantity
        cost = Decimal(0)
        for lot in lots[key]:
            if remaining <= 0:
                break
            matched = min(lot.quantity, remaining)
            allocated_cost = lot.cost * matched / lot.quantity
            lot.quantity -= matched
            lot.cost -= allocated_cost
            remaining -= matched
            cost += allocated_cost
        if remaining > 0:
            raise ValueError("sell fill exceeds the available FIFO position")
        realized[fill.quote] += notional - fill.fee - cost
        lots[key] = [lot for lot in lots[key] if lot.quantity > 0]

    open_cost: dict[str, Decimal] = defaultdict(Decimal)
    for (_, quote), quote_lots in lots.items():
        open_cost[quote] += sum((lot.cost for lot in quote_lots), Decimal(0))
    currencies = sorted(set(realized) | set(open_cost))
    return tuple(
        QuotePerformance(
            quote=quote,
            realized_pnl=realized[quote],
            open_cost_basis=open_cost[quote],
        )
        for quote in currencies
    )


@dataclass(frozen=True)
class OpenPosition:
    """What is still held of one asset: FIFO average entry price and the oldest open buy."""

    quantity: Decimal
    average_price: Decimal
    held_since: datetime


def open_positions(fills: Iterable[FillRow]) -> dict[str, OpenPosition]:
    """Open FIFO lots per base asset, oldest fills first.

    Unlike `compute_fifo_performance` this tolerates sells beyond the known lots (coins that were
    already in the account before the bot): those holdings have no known entry and are omitted.
    """
    lots: dict[str, list[tuple[Decimal, Decimal, datetime]]] = defaultdict(list)
    for fill in fills:
        if fill.side == "BUY":
            lots[fill.base].append((fill.quantity, fill.price, fill.filled_at))
            continue
        remaining = fill.quantity
        kept = []
        for quantity, price, filled_at in lots[fill.base]:
            matched = min(quantity, remaining)
            remaining -= matched
            if quantity > matched:
                kept.append((quantity - matched, price, filled_at))
        lots[fill.base] = kept
    positions = {}
    for base, open_lots in lots.items():
        quantity = sum((lot[0] for lot in open_lots), Decimal(0))
        if quantity > 0:
            positions[base] = OpenPosition(
                quantity=quantity,
                average_price=sum((lot[0] * lot[1] for lot in open_lots), Decimal(0)) / quantity,
                held_since=open_lots[0][2],
            )
    return positions
