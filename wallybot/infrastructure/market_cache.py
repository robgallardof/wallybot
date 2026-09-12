import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from wallybot.domain.market import Instrument, MarketSnapshot


class RedisLike(Protocol):
    """The narrow slice of redis.asyncio.Redis this cache actually uses."""

    async def set(self, key: str, value: str, px: int | None = None) -> object: ...

    async def get(self, key: str) -> bytes | None: ...


class MarketCache:
    """Redis-backed hot tier for validated snapshots (ADR-003).

    Disposable acceleration only: a cache hit is not proof of freshness. Per ADR-003, cache
    expiry never implies valid fresh market data -- this class stores and returns exactly what
    it was given, timestamp included, and never claims a snapshot is fresh. Callers still run
    the data quality gate (wallybot/data/quality.py) or check the snapshot's own timestamp
    before trusting it for a risk-increasing decision.
    """

    def __init__(self, redis: RedisLike) -> None:
        self.redis = redis

    def _key(self, instrument: Instrument) -> str:
        return f"market:snapshot:{instrument.id}"

    async def set_snapshot(self, snapshot: MarketSnapshot, ttl: timedelta) -> None:
        payload = json.dumps(
            {
                "instrument_id": snapshot.instrument.id,
                "bid": str(snapshot.bid),
                "ask": str(snapshot.ask),
                "timestamp": snapshot.timestamp.isoformat(),
                "source": snapshot.source,
            }
        )
        px = round(ttl / timedelta(milliseconds=1))
        await self.redis.set(self._key(snapshot.instrument), payload, px=px)

    async def get_snapshot(self, instrument: Instrument) -> MarketSnapshot | None:
        raw = await self.redis.get(self._key(instrument))
        if raw is None:
            return None
        data = json.loads(raw)
        if data["instrument_id"] != instrument.id:
            raise ValueError("cached snapshot instrument mismatch")
        return MarketSnapshot(
            instrument=instrument,
            bid=Decimal(data["bid"]),
            ask=Decimal(data["ask"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
        )
