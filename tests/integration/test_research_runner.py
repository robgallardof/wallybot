import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.research_runner import run_pending_research_job
from wallybot.data.historical import HistoricalStore
from wallybot.domain.experiment import ExperimentRecord
from wallybot.domain.market import Candle, Instrument, MarketType
from wallybot.domain.research_job import ResearchJobStatus
from wallybot.infrastructure.experiment_repository import ExperimentRepository
from wallybot.infrastructure.models import JobRow
from wallybot.infrastructure.research_job_repository import ResearchJobRepository

pytestmark = pytest.mark.integration

INSTRUMENT = Instrument(
    venue="kraken",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
WINDOW_START = datetime(2026, 1, 1, tzinfo=UTC)
NOW = datetime(2026, 1, 10, tzinfo=UTC)
# Rise-then-fall series, same shape test_backtest_orchestrator.py uses: exactly one round trip.
PRICES = ["100", "101", "102", "103", "104", "105", "104", "103", "102", "101", "100"]


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
def _reset_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE jobs, experiment_records CASCADE")
    yield


def make_record(**overrides) -> ExperimentRecord:
    fields: dict[str, object] = {
        "experiment_id": "exp-original",
        "strategy_id": "trend_following",
        "strategy_version": 1,
        "feature_engine_version": 1,
        "backtest_engine_version": 1,
        "instrument_venue": INSTRUMENT.venue,
        "instrument_market_type": str(INSTRUMENT.market_type),
        "instrument_base": INSTRUMENT.base,
        "instrument_quote": INSTRUMENT.quote,
        "price_increment": INSTRUMENT.price_increment,
        "quantity_increment": INSTRUMENT.quantity_increment,
        "min_quantity": INSTRUMENT.min_quantity,
        "timeframe": "1h",
        "window_start": WINDOW_START,
        "window_end": WINDOW_START + timedelta(hours=len(PRICES)),
        "feature_window": 3,
        "risk_off_threshold": Decimal("0.5"),
        "fee_rate": Decimal("0"),
        "slippage_pct": Decimal("0"),
        "starting_equity": Decimal("10000"),
        "allocation_pct": Decimal("1"),
        "seed": None,
        "trade_count": 1,
        "final_equity": Decimal("10500"),
        "total_return_pct": Decimal("0.05"),
        "max_drawdown_pct": Decimal("0.02"),
        "win_rate": Decimal("1"),
        "created_at": NOW,
    }
    fields.update(overrides)
    return ExperimentRecord(**fields)  # type: ignore[arg-type]


def write_fixture(tmp_path: Path) -> None:
    class FixedClock:
        def now(self) -> datetime:
            return datetime(2026, 1, 11, tzinfo=UTC)

    class SequentialIds:
        def __init__(self) -> None:
            self.n = 0

        def new_id(self) -> str:
            self.n += 1
            return f"part{self.n}"

    candles = []
    for i, price in enumerate(PRICES):
        open_time = WINDOW_START + timedelta(hours=i)
        candles.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=Decimal(price),
                high=Decimal(price),
                low=Decimal(price),
                close=Decimal(price),
                volume=Decimal("10"),
                source="kraken",
                received_at=open_time + timedelta(hours=1),
            )
        )
    HistoricalStore(tmp_path, FixedClock(), SequentialIds()).write_partition(candles, "PASS")


async def test_a_claimed_job_reruns_the_backtest_and_completes(sessions, tmp_path) -> None:
    write_fixture(tmp_path)
    async with sessions.begin() as db:
        await ExperimentRepository(db).save(make_record())
    async with sessions.begin() as db:
        db.add(
            JobRow(
                id="job-1",
                kind="RESEARCH",
                scheduled_at=0,
                status=ResearchJobStatus.PENDING.value,
                attempts=0,
                payload={"experiment_id": "exp-original", "purpose": "reproduce"},
            )
        )

    await run_pending_research_job(sessions, tmp_path, now=100)

    job = await ResearchJobRepository(sessions).get("job-1")
    assert job.status == ResearchJobStatus.COMPLETED.value
    assert job.artifact_uri is not None
    assert job.artifact_uri != "exp-original"  # a new experiment, not the original

    async with sessions() as db:
        new_record = await ExperimentRepository(db).get(job.artifact_uri)
    assert new_record is not None
    assert new_record.trade_count == 1
    assert new_record.instrument_base == "BTC"


async def test_a_missing_experiment_fails_the_job_with_a_reason(sessions, tmp_path) -> None:
    async with sessions.begin() as db:
        db.add(
            JobRow(
                id="job-2",
                kind="RESEARCH",
                scheduled_at=0,
                status=ResearchJobStatus.PENDING.value,
                attempts=0,
                payload={"experiment_id": "does-not-exist", "purpose": "reproduce"},
            )
        )

    await run_pending_research_job(sessions, tmp_path, now=200)

    job = await ResearchJobRepository(sessions).get("job-2")
    assert job.status == ResearchJobStatus.FAILED.value
    assert "does-not-exist" in job.error


async def test_no_pending_job_is_a_no_op(sessions, tmp_path) -> None:
    await run_pending_research_job(sessions, tmp_path, now=300)  # must not raise
