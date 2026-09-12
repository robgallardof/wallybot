from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class MarketType(StrEnum):
    SPOT = "SPOT"


TIMEFRAME_DURATIONS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def _require_utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) != timedelta(0):
        raise ValueError(f"{field} must be an aware UTC datetime")


@dataclass(frozen=True)
class Instrument:
    """Identity never assumes a bare symbol is unique across venues or market types."""

    venue: str
    market_type: MarketType
    base: str
    quote: str
    price_increment: Decimal
    quantity_increment: Decimal
    min_quantity: Decimal

    def __post_init__(self) -> None:
        if not self.venue or not self.base or not self.quote:
            raise ValueError("venue, base and quote are required")
        for field, value in (
            ("price_increment", self.price_increment),
            ("quantity_increment", self.quantity_increment),
            ("min_quantity", self.min_quantity),
        ):
            if value <= 0:
                raise ValueError(f"{field} must be positive")

    @property
    def id(self) -> str:
        return f"{self.venue}:{self.market_type}:{self.base}/{self.quote}"


@dataclass(frozen=True)
class Candle:
    instrument: Instrument
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str
    received_at: datetime

    def __post_init__(self) -> None:
        if not self.timeframe or not self.source:
            raise ValueError("timeframe and source are required")
        _require_utc(self.open_time, "open_time")
        _require_utc(self.close_time, "close_time")
        _require_utc(self.received_at, "received_at")
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        for field, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("close", self.close),
        ):
            if value <= 0 or not value.is_finite():
                raise ValueError(f"{field} must be a finite positive price")
        if self.volume < 0 or not self.volume.is_finite():
            raise ValueError("volume must be a finite nonnegative quantity")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("low/high must bound open and close")


@dataclass(frozen=True)
class MarketSnapshot:
    """Best bid/ask at a point in time. Never a substitute for order-book depth."""

    instrument: Instrument
    bid: Decimal
    ask: Decimal
    timestamp: datetime
    source: str

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source is required")
        _require_utc(self.timestamp, "timestamp")
        if self.bid <= 0 or not self.bid.is_finite():
            raise ValueError("bid must be a finite positive price")
        if self.ask <= 0 or not self.ask.is_finite():
            raise ValueError("ask must be a finite positive price")
        if self.ask < self.bid:
            raise ValueError("ask must not be below bid (crossed market)")

    @property
    def spread_ratio(self) -> Decimal:
        return (self.ask - self.bid) / self.ask


class MarketDataProvider(Protocol):
    """Discovers instruments and fetches candles/snapshots. Never holds trading credentials."""

    async def discover_instruments(self) -> list[Instrument]: ...

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]: ...

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot: ...
