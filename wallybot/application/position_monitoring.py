"""Read-only FIFO attribution and conservative marks for confirmed PAPER fills."""

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from wallybot.domain.market import Instrument, MarketDataProvider, MarketSnapshot, MarketType
from wallybot.infrastructure.models import FillRow


@dataclass
class FillPosition:
    remaining_quantity: Decimal
    remaining_cost: Decimal
    realized_pnl: Decimal = Decimal(0)
    closed_at: datetime | None = None


def attribute_fifo_positions(fills: Iterable[FillRow]) -> dict[str, FillPosition]:
    """Attribute closures to their entry fills; sale results are also available for review.

    Entry and sale results describe the same closure from two perspectives and must never be
    summed together. Account totals remain the responsibility of compute_fifo_performance.
    """
    positions: dict[str, FillPosition] = {}
    lots: dict[tuple[str, str], list[str]] = defaultdict(list)
    for fill in fills:
        if fill.fill_id in positions:
            raise ValueError("duplicate fill in FIFO history")
        if fill.quantity <= 0 or not fill.quantity.is_finite():
            raise ValueError("invalid fill quantity")
        if not fill.price.is_finite() or fill.price <= 0:
            raise ValueError("invalid fill price")
        if not fill.fee.is_finite() or fill.fee < 0 or fill.fee_currency != fill.quote:
            raise ValueError("FIFO monitoring requires nonnegative quote-currency fees")
        key = (fill.base, fill.quote)
        if fill.side == "BUY":
            positions[fill.fill_id] = FillPosition(
                fill.quantity, fill.quantity * fill.price + fill.fee
            )
            lots[key].append(fill.fill_id)
            continue
        if fill.side != "SELL":
            raise ValueError("unsupported fill side")
        remaining = fill.quantity
        proceeds = fill.quantity * fill.price - fill.fee
        result = FillPosition(Decimal(0), Decimal(0), closed_at=fill.filled_at)
        for entry_id in lots[key]:
            if remaining == 0:
                break
            entry = positions[entry_id]
            matched = min(remaining, entry.remaining_quantity)
            cost = entry.remaining_cost * matched / entry.remaining_quantity
            # Allocate the final remainder exactly, avoiding accumulating Decimal rounding drift.
            net = proceeds if matched == remaining else proceeds * matched / remaining
            entry.remaining_quantity -= matched
            entry.remaining_cost -= cost
            entry.realized_pnl += net - cost
            result.realized_pnl += net - cost
            if entry.remaining_quantity == 0:
                entry.closed_at = fill.filled_at
            remaining -= matched
            proceeds -= net
        if remaining > 0:
            raise ValueError("sell fill exceeds the available FIFO position")
        lots[key] = [item for item in lots[key] if positions[item].remaining_quantity > 0]
        positions[fill.fill_id] = result
    return positions


def trustworthy_mark(snapshot: MarketSnapshot, instrument: Instrument, now: datetime) -> bool:
    """Display policy: same instrument, at most 60s old, no future/crossed/wide quote."""
    return (
        snapshot.instrument.id == instrument.id
        and snapshot.source == instrument.venue
        and timedelta(0) <= now - snapshot.timestamp <= timedelta(seconds=60)
        and snapshot.bid.is_finite()
        and snapshot.ask.is_finite()
        and Decimal(0) < snapshot.bid <= snapshot.ask
        and snapshot.spread_ratio <= Decimal("0.05")
    )


async def fetch_position_marks(
    provider: MarketDataProvider | None, fills: Iterable[FillRow]
) -> dict[tuple[str, str, str], MarketSnapshot]:
    """Bound public-data work; an unavailable quote never prevents reading the ledger."""
    if provider is None:
        return {}
    instruments = {
        (fill.venue, fill.base, fill.quote): Instrument(
            fill.venue, MarketType.SPOT, fill.base, fill.quote
        )
        for fill in fills
    }
    semaphore = asyncio.Semaphore(4)

    async def fetch(key: tuple[str, str, str], instrument: Instrument):
        async with semaphore:
            try:
                async with asyncio.timeout(3):
                    snapshot = await provider.fetch_snapshot(instrument)
                return key, snapshot
            except Exception:
                return None

    try:
        async with asyncio.timeout(5):
            results = await asyncio.gather(*(fetch(k, v) for k, v in instruments.items()))
    except TimeoutError:
        return {}
    return dict(item for item in results if item is not None)


def level_status(
    remaining: Decimal, price: Decimal | None, stop: Decimal | None, target: Decimal | None
) -> str:
    if remaining == 0:
        return "CLOSED"
    if price is None:
        return "QUOTE_UNAVAILABLE"
    if stop is not None and price <= stop:
        return "STOP_REACHED"
    if target is not None and price >= target:
        return "TARGET_REACHED"
    return "MONITORING"
