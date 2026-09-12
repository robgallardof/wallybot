import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from redis.asyncio import Redis

from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.infrastructure.market_cache import MarketCache

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


def make_snapshot(**overrides) -> MarketSnapshot:
    fields = {
        "instrument": INSTRUMENT,
        "bid": Decimal("59990.12"),
        "ask": Decimal("60000.34"),
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "source": "fake",
    }
    fields.update(overrides)
    return MarketSnapshot(**fields)


@pytest.fixture
async def redis_client(dependencies):
    _, redis_url = dependencies
    client = Redis.from_url(redis_url)
    yield client
    await client.flushdb()
    await client.aclose()


async def test_get_snapshot_returns_stored_value(redis_client):
    cache = MarketCache(redis_client)
    snapshot = make_snapshot()
    await cache.set_snapshot(snapshot, ttl=timedelta(minutes=5))
    result = await cache.get_snapshot(snapshot.instrument)
    assert result == snapshot


async def test_get_snapshot_returns_none_on_miss(redis_client):
    cache = MarketCache(redis_client)
    result = await cache.get_snapshot(INSTRUMENT)
    assert result is None


async def test_snapshot_expires_after_ttl(redis_client):
    cache = MarketCache(redis_client)
    await cache.set_snapshot(make_snapshot(), ttl=timedelta(milliseconds=50))
    await asyncio.sleep(0.3)
    result = await cache.get_snapshot(INSTRUMENT)
    assert result is None


async def test_cache_presence_does_not_imply_freshness(redis_client):
    # ADR-003: cache expiry never implies valid fresh market data. A stale snapshot can sit
    # in the cache, unexpired, and the cache must return it unchanged -- it is the caller's
    # job (the quality gate) to notice the timestamp is old, not the cache's.
    stale = make_snapshot(timestamp=datetime(2020, 1, 1, tzinfo=UTC))
    cache = MarketCache(redis_client)
    await cache.set_snapshot(stale, ttl=timedelta(hours=1))
    result = await cache.get_snapshot(INSTRUMENT)
    assert result is not None
    assert result.timestamp == stale.timestamp


async def test_rejects_mismatched_instrument_at_the_same_key():
    # Defensive check: MarketCache keys by instrument.id, so a mismatch here would mean a key
    # collision bug, not normal usage -- verified directly against a fake in-memory client.
    class FakeRedis:
        def __init__(self) -> None:
            self.store: dict[str, bytes] = {}

        async def set(self, key, value, px=None):
            self.store[key] = value.encode() if isinstance(value, str) else value

        async def get(self, key):
            return self.store.get(key)

    other = Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base="ETH",
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
    )
    fake_redis = FakeRedis()
    cache = MarketCache(fake_redis)
    await cache.set_snapshot(make_snapshot(), ttl=timedelta(minutes=1))
    # Force a collision by reading BTC's payload back out under ETH's key.
    fake_redis.store[cache._key(other)] = fake_redis.store[cache._key(INSTRUMENT)]
    with pytest.raises(ValueError):
        await cache.get_snapshot(other)
