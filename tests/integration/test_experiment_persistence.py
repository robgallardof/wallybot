import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.experiment import ExperimentRecord
from wallybot.infrastructure.experiment_repository import ExperimentRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)
WINDOW_START = datetime(2026, 1, 1, tzinfo=UTC)
WINDOW_END = datetime(2026, 1, 8, tzinfo=UTC)


def make_record(**overrides) -> ExperimentRecord:
    fields: dict[str, object] = {
        "experiment_id": "exp-1",
        "strategy_id": "trend_following",
        "strategy_version": 1,
        "feature_engine_version": 1,
        "backtest_engine_version": 1,
        "instrument_venue": "kraken",
        "instrument_base": "BTC",
        "instrument_quote": "USD",
        "timeframe": "1h",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "feature_window": 20,
        "risk_off_threshold": Decimal("0.1"),
        "fee_rate": Decimal("0.001"),
        "slippage_pct": Decimal("0.0005"),
        "starting_equity": Decimal("10000"),
        "allocation_pct": Decimal("0.1"),
        "seed": 42,
        "trade_count": 3,
        "final_equity": Decimal("10500"),
        "total_return_pct": Decimal("0.05"),
        "max_drawdown_pct": Decimal("0.02"),
        "win_rate": Decimal("0.667"),
        "created_at": NOW,
    }
    fields.update(overrides)
    return ExperimentRecord(**fields)  # type: ignore[arg-type]


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_experiments_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE experiment_records CASCADE")
    yield


async def test_a_saved_record_round_trips_exactly(sessions) -> None:
    record = make_record()
    async with sessions.begin() as session:
        await ExperimentRepository(session).save(record)

    async with sessions() as session:
        fetched = await ExperimentRepository(session).get("exp-1")

    assert fetched == record


async def test_get_returns_none_for_an_unknown_experiment_id(sessions) -> None:
    async with sessions() as session:
        fetched = await ExperimentRepository(session).get("does-not-exist")
    assert fetched is None


async def test_rerunning_the_same_strategy_never_overwrites_the_prior_record(sessions) -> None:
    first = make_record(experiment_id="exp-1", final_equity=Decimal("10500"))
    second = make_record(experiment_id="exp-2", final_equity=Decimal("9800"))
    async with sessions.begin() as session:
        repo = ExperimentRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        history = await ExperimentRepository(session).list_recent("trend_following")

    assert len(history) == 2
    assert {r.experiment_id for r in history} == {"exp-1", "exp-2"}
