import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.price_consensus_job import ProviderSource, run_price_consensus_tick
from wallybot.domain.market import Candle, Instrument
from wallybot.infrastructure.price_consensus_repository import PriceConsensusRepository
from wallybot.infrastructure.provider_reliability_repository import ProviderReliabilityRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_tables(dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE price_consensus_results, provider_reliability_snapshots")
    yield


class FakeCandleProvider:
    def __init__(self, price: str) -> None:
        self.price = price

    async def discover_instruments(self) -> list[Instrument]:
        raise NotImplementedError

    async def fetch_candles(self, instrument, timeframe, since, limit):
        return [
            Candle(
                instrument=instrument,
                timeframe="1m",
                open_time=NOW - timedelta(minutes=1),
                close_time=NOW,
                open=Decimal(self.price),
                high=Decimal(self.price),
                low=Decimal(self.price),
                close=Decimal(self.price),
                volume=Decimal("1"),
                source=instrument.venue,
                received_at=NOW,
            )
        ]

    async def fetch_snapshot(self, instrument):
        raise NotImplementedError


async def test_a_tick_persists_consensus_and_reliability_rows(sessions) -> None:
    sources = [
        ProviderSource("kraken", FakeCandleProvider("100")),
        ProviderSource("tiingo", FakeCandleProvider("100.2")),
    ]
    outcomes = {}

    await run_price_consensus_tick(sessions, sources, NOW, outcomes)

    async with sessions() as db:
        consensus_rows = await PriceConsensusRepository(db).list_latest()
        reliability_rows = await ProviderReliabilityRepository(db).list_latest()

    assert {row.instrument_id for row in consensus_rows} == {"BTC/USD", "ETH/USD"}
    assert all(row.consensus_price is not None for row in consensus_rows)
    assert {row.provider for row in reliability_rows} == {"kraken", "tiingo"}
