from datetime import UTC, datetime, timedelta

from tests.contract.market_data_provider_suite import (
    FixedClock,
    assert_discovers_valid_instruments,
    assert_fetches_candles_respecting_since_and_limit,
    assert_fetches_valid_snapshot,
)
from wallybot.exchanges.fake import FakeExchange


def make_provider() -> FakeExchange:
    return FakeExchange(clock=FixedClock(datetime(2026, 1, 1, tzinfo=UTC)), seed=1)


async def test_discovers_valid_instruments() -> None:
    await assert_discovers_valid_instruments(make_provider())


async def test_fetches_candles_respecting_since_and_limit() -> None:
    since = datetime(2026, 1, 1, tzinfo=UTC) - timedelta(hours=2)
    await assert_fetches_candles_respecting_since_and_limit(make_provider(), "1h", since, limit=2)


async def test_fetches_valid_snapshot() -> None:
    await assert_fetches_valid_snapshot(make_provider())


async def test_rejects_unsupported_timeframe() -> None:
    provider = make_provider()
    instrument = (await provider.discover_instruments())[0]
    try:
        await provider.fetch_candles(instrument, "3m", datetime(2026, 1, 1, tzinfo=UTC), 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unsupported timeframe")


async def test_deterministic_for_same_seed() -> None:
    since = datetime(2026, 1, 1, tzinfo=UTC) - timedelta(hours=3)
    a = await make_provider().fetch_candles(
        (await make_provider().discover_instruments())[0], "1h", since, 3
    )
    b = await make_provider().fetch_candles(
        (await make_provider().discover_instruments())[0], "1h", since, 3
    )
    assert a == b
