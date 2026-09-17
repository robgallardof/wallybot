import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.decision_loop import run_decision_tick
from wallybot.application.execution_service import ExecutionService
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.data.quality import QualityPolicy
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType
from wallybot.domain.order import OrderStatus
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.models import FillRow, LedgerPostingRow, OrderIntentRow
from wallybot.market.universe import UniverseFilterConfig

pytestmark = pytest.mark.integration

ACCOUNT_ID = "paper:decision-loop-user"
NOW = datetime(2026, 1, 2, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="test",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


class SequentialIdGenerator:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"id-{self.counter}"


def _uptrend_candles(window: int, closes: list[Decimal]) -> list[Candle]:
    candles = []
    for i, close in enumerate(closes):
        open_time = NOW - timedelta(hours=window - i)
        close_time = open_time + timedelta(hours=1)
        candles.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=close_time,
                open=close,
                high=close + Decimal("1"),
                low=close - Decimal("1"),
                close=close,
                volume=Decimal("10"),
                source="test",
                received_at=close_time,
            )
        )
    return candles


class ControlledProvider:
    """A guaranteed-uptrend MarketDataProvider, same shape as
    tests/integration/test_decision_pipeline.py's own -- deterministic BUY, independent of any
    seed's luck."""

    def __init__(self, candles: list[Candle], snapshot: MarketSnapshot) -> None:
        self.candles = candles
        self.snapshot = snapshot

    async def discover_instruments(self) -> list[Instrument]:
        return [INSTRUMENT]

    async def fetch_candles(self, instrument, timeframe, since, limit) -> list[Candle]:
        return [c for c in self.candles if c.open_time >= since][:limit]

    async def fetch_snapshot(self, instrument) -> MarketSnapshot:
        return self.snapshot


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE equity_snapshots, ledger_postings, ledger_transactions, "
            "ledger_accounts, fills, order_transitions, order_intents CASCADE"
        )
    yield


def _seed_cash(db, account_id: str, amount: str) -> None:
    value = Decimal(amount)
    own_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES (%s, 'USD', 'CASH') RETURNING id""",
        (account_id,),
    ).fetchone()[0]
    clearing_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES ('clearing', 'USD', 'CLEARING')
           ON CONFLICT (account_id, currency, purpose) DO UPDATE SET currency = EXCLUDED.currency
           RETURNING id""",
    ).fetchone()[0]
    transaction_id = str(uuid4())
    db.execute(
        """INSERT INTO ledger_transactions
           (transaction_id, account_id, reason, reference_id, recorded_at)
           VALUES (%s, %s, 'INITIAL_FUNDING', %s, NOW())""",
        (transaction_id, account_id, transaction_id),
    )
    db.execute(
        """INSERT INTO ledger_postings (transaction_id, ledger_account_id, amount)
           VALUES (%s, %s, %s), (%s, %s, %s)""",
        (transaction_id, own_account, value, transaction_id, clearing_account, -value),
    )


def make_provider() -> ControlledProvider:
    closes = [Decimal(50000 + i * 1000) for i in range(20)]
    candles = _uptrend_candles(20, closes)
    snapshot = MarketSnapshot(
        instrument=INSTRUMENT, bid=Decimal("68990"), ask=Decimal("69010"), timestamp=NOW,
        source="test",
    )
    return ControlledProvider(candles, snapshot)


def make_universe_config() -> UniverseFilterConfig:
    return UniverseFilterConfig(
        version=1,
        min_history_candles=20,
        min_average_quote_volume=Decimal("0"),
        max_spread_ratio=Decimal("0.05"),
    )


def make_quality_policy() -> QualityPolicy:
    return QualityPolicy(
        version=1,
        timeframe="1h",
        max_stale_age=timedelta(hours=3),
        max_clock_drift=timedelta(minutes=5),
        max_abnormal_return=Decimal("0.5"),
    )


async def test_a_funded_account_places_a_real_paper_order_end_to_end(sessions, db) -> None:
    _seed_cash(db, ACCOUNT_ID, "10000")
    provider = make_provider()
    paper_gateway = FakeExchange(clock=FixedClock(NOW), market_data=provider)
    execution = ExecutionService(gateway=paper_gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    result = await run_decision_tick(
        sessions=sessions,
        provider=provider,
        paper_gateway=paper_gateway,
        execution=execution,
        reconciliation=reconciliation,
        clock=FixedClock(NOW),
        id_generator=SequentialIdGenerator(),
        quality_policy=make_quality_policy(),
        universe_config=make_universe_config(),
        account_id=ACCOUNT_ID,
        now=NOW,
    )

    assert result.reconciliation_healthy is True
    assert len(result.outcomes) == 1
    outcome = result.outcomes[0]
    assert outcome.order_status is OrderStatus.FILLED

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert len(rows) == 1
        assert rows[0].account_id == ACCOUNT_ID
        assert rows[0].status == OrderStatus.FILLED

        fills = (await session.execute(select(FillRow))).scalars().all()
        assert len(fills) == 1

        postings = (await session.execute(select(LedgerPostingRow))).scalars().all()
        # 2 from the seeded initial-funding transaction + 4 from the fill's own balanced legs.
        assert len(postings) == 6


async def test_an_unfunded_account_places_no_order(sessions, db) -> None:
    # No _seed_cash call -- assess_equity would raise on zero equity before the pipeline could
    # even run, same fail-closed behavior the loop wrapper's own try/except relies on.
    provider = make_provider()
    paper_gateway = FakeExchange(clock=FixedClock(NOW), market_data=provider)
    execution = ExecutionService(gateway=paper_gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    with pytest.raises(ValueError, match="non-positive equity"):
        await run_decision_tick(
            sessions=sessions,
            provider=provider,
            paper_gateway=paper_gateway,
            execution=execution,
            reconciliation=reconciliation,
            clock=FixedClock(NOW),
            id_generator=SequentialIdGenerator(),
            quality_policy=make_quality_policy(),
            universe_config=make_universe_config(),
            account_id=ACCOUNT_ID,
            now=NOW,
        )

    async with sessions() as session:
        rows = (await session.execute(select(OrderIntentRow))).scalars().all()
        assert rows == []


async def test_the_gateways_simulated_balance_resyncs_from_the_ledger_each_tick(
    sessions, db
) -> None:
    _seed_cash(db, ACCOUNT_ID, "10000")
    provider = make_provider()
    paper_gateway = FakeExchange(clock=FixedClock(NOW), balances={"USD": Decimal("999999999")})
    execution = ExecutionService(gateway=paper_gateway, sessions=sessions, clock=FixedClock(NOW))
    reconciliation = ReconciliationService(execution=execution, sessions=sessions)

    await run_decision_tick(
        sessions=sessions,
        provider=provider,
        paper_gateway=paper_gateway,
        execution=execution,
        reconciliation=reconciliation,
        clock=FixedClock(NOW),
        id_generator=SequentialIdGenerator(),
        quality_policy=make_quality_policy(),
        universe_config=make_universe_config(),
        account_id=ACCOUNT_ID,
        now=NOW,
    )

    # The stale pre-existing balance the gateway was constructed with never survives -- it is
    # overwritten from the real ledger (10000, not 999999999) at the start of the tick.
    assert paper_gateway.balances["USD"] < Decimal("10000")
