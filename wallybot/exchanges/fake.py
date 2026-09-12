import random
from datetime import datetime
from decimal import Decimal

from wallybot.domain.clock import Clock
from wallybot.domain.market import (
    TIMEFRAME_DURATIONS,
    Candle,
    Instrument,
    MarketSnapshot,
    MarketType,
)


class FakeExchange:
    """Seeded, network-free MarketDataProvider for deterministic tests and local dev.

    No trading credentials, no balances or order capability -- those belong to the
    Phase 4 paper-execution slice, once something needs them.
    """

    def __init__(self, clock: Clock, seed: int = 0) -> None:
        self.clock = clock
        self.seed = seed
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
            close_price = max(price + drift, instrument.price_increment)
            wick = Decimal(rng.uniform(0, 0.005)) * price
            high = max(price, close_price) + wick
            low = max(min(price, close_price) - wick, instrument.price_increment)
            volume = Decimal(rng.uniform(0.1, 10)).quantize(instrument.quantity_increment)
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=price.quantize(instrument.price_increment),
                    high=high.quantize(instrument.price_increment),
                    low=low.quantize(instrument.price_increment),
                    close=close_price.quantize(instrument.price_increment),
                    volume=volume,
                    source="fake",
                    received_at=now,
                )
            )
            price = close_price
            open_time = close_time
        return candles

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        pair = f"{instrument.base}/{instrument.quote}"
        mid = self._base_price.get(pair, Decimal("100"))
        rng = random.Random(f"{self.seed}:{instrument.id}:snapshot:{self.clock.now().isoformat()}")
        half_spread = mid * Decimal(rng.uniform(0.0001, 0.0015))
        return MarketSnapshot(
            instrument=instrument,
            bid=(mid - half_spread).quantize(instrument.price_increment),
            ask=(mid + half_spread).quantize(instrument.price_increment),
            timestamp=self.clock.now(),
            source="fake",
        )
