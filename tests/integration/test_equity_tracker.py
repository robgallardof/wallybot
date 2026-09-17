import asyncio
import sys
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.equity_tracker import UnpricedPositionError, assess_equity
from wallybot.domain.market import Instrument, MarketSnapshot, MarketType
from wallybot.domain.portfolio import Bucket

pytestmark = pytest.mark.integration

ACCOUNT_ID = "paper:equity-test-user"
NOW = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)
BTC_USD = Instrument(
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


class FakeProvider:
    def __init__(self, instruments: list[Instrument], snapshot: MarketSnapshot) -> None:
        self.instruments = instruments
        self.snapshot = snapshot

    async def discover_instruments(self) -> list[Instrument]:
        return self.instruments

    async def fetch_candles(self, instrument, timeframe, since, limit):
        return []

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
            "ledger_accounts CASCADE"
        )
    yield


def _seed_balance(db, account_id: str, currency: str, purpose: str, amount: str) -> None:
    value = Decimal(amount)
    own_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES (%s, %s, %s) RETURNING id""",
        (account_id, currency, purpose),
    ).fetchone()[0]
    clearing_account = db.execute(
        """INSERT INTO ledger_accounts (account_id, currency, purpose)
           VALUES ('clearing', %s, 'CLEARING')
           ON CONFLICT (account_id, currency, purpose) DO UPDATE SET currency = EXCLUDED.currency
           RETURNING id""",
        (currency,),
    ).fetchone()[0]
    transaction_id = str(uuid4())
    db.execute(
        """INSERT INTO ledger_transactions
           (transaction_id, account_id, reason, reference_id, recorded_at)
           VALUES (%s, %s, 'FILL', %s, NOW())""",
        (transaction_id, account_id, transaction_id),
    )
    db.execute(
        """INSERT INTO ledger_postings (transaction_id, ledger_account_id, amount)
           VALUES (%s, %s, %s), (%s, %s, %s)""",
        (transaction_id, own_account, value, transaction_id, clearing_account, -value),
    )


async def test_cash_only_account_has_equity_equal_to_cash(sessions, db) -> None:
    _seed_balance(db, ACCOUNT_ID, "USD", "CASH", "10000")
    provider = FakeProvider([BTC_USD], MarketSnapshot(
        instrument=BTC_USD, bid=Decimal("50000"), ask=Decimal("50010"), timestamp=NOW,
        source="test",
    ))

    assessment = await assess_equity(
        sessions, provider, ACCOUNT_ID, "PAPER", "USD", Bucket.CORE, NOW
    )

    assert assessment.portfolio_state.equity == Decimal("10000")
    assert assessment.portfolio_state.asset_exposure == {}
    assert assessment.portfolio_state.open_positions == 0
    assert assessment.daily_loss == Decimal("0")
    assert assessment.weekly_loss == Decimal("0")
    assert assessment.drawdown == Decimal("0")


async def test_a_held_position_is_marked_to_market_and_added_to_equity(sessions, db) -> None:
    _seed_balance(db, ACCOUNT_ID, "USD", "CASH", "5000")
    _seed_balance(db, ACCOUNT_ID, "BTC", "POSITION", "0.1")
    provider = FakeProvider([BTC_USD], MarketSnapshot(
        instrument=BTC_USD, bid=Decimal("49990"), ask=Decimal("50010"), timestamp=NOW,
        source="test",
    ))

    assessment = await assess_equity(
        sessions, provider, ACCOUNT_ID, "PAPER", "USD", Bucket.CORE, NOW
    )

    # mid price 50000 * 0.1 BTC = 5000 notional, plus 5000 cash.
    assert assessment.portfolio_state.equity == Decimal("10000")
    assert assessment.portfolio_state.asset_exposure == {BTC_USD.id: Decimal("5000")}
    assert assessment.portfolio_state.bucket_exposure == {Bucket.CORE: Decimal("5000")}
    assert assessment.portfolio_state.open_positions == 1


async def test_an_unpriceable_held_position_fails_closed(sessions, db) -> None:
    _seed_balance(db, ACCOUNT_ID, "USD", "CASH", "1000")
    _seed_balance(db, ACCOUNT_ID, "XYZ", "POSITION", "5")
    provider = FakeProvider([BTC_USD], MarketSnapshot(
        instrument=BTC_USD, bid=Decimal("50000"), ask=Decimal("50010"), timestamp=NOW,
        source="test",
    ))

    with pytest.raises(UnpricedPositionError):
        await assess_equity(sessions, provider, ACCOUNT_ID, "PAPER", "USD", Bucket.CORE, NOW)


async def test_repeated_calls_track_a_persistent_high_water_mark_and_drawdown(
    sessions, db
) -> None:
    _seed_balance(db, ACCOUNT_ID, "USD", "CASH", "10000")
    provider = FakeProvider([BTC_USD], MarketSnapshot(
        instrument=BTC_USD, bid=Decimal("50000"), ask=Decimal("50010"), timestamp=NOW,
        source="test",
    ))
    first = await assess_equity(sessions, provider, ACCOUNT_ID, "PAPER", "USD", Bucket.CORE, NOW)
    assert first.drawdown == Decimal("0")

    # Cash drops (simulating a loss elsewhere) -- equity falls below the persisted high-water
    # mark from the first call, even though this is an entirely separate function call/process
    # tick, proving the high-water mark survives across calls (RISK.md: "restarting cannot reset
    # losses").
    db.execute("UPDATE ledger_postings SET amount = amount - 1000 WHERE amount > 0")
    later = NOW.replace(hour=13)
    second = await assess_equity(
        sessions, provider, ACCOUNT_ID, "PAPER", "USD", Bucket.CORE, later
    )

    assert second.portfolio_state.equity == Decimal("9000")
    assert second.drawdown == Decimal("1000") / Decimal("10000")
    assert second.daily_loss == Decimal("1000") / Decimal("10000")
