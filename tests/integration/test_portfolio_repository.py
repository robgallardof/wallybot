import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.infrastructure.portfolio_repository import PortfolioRepository

pytestmark = pytest.mark.integration

ACCOUNT_ID = "paper:fees-test-user"
NOW = datetime(2026, 1, 8, 12, 0, tzinfo=UTC)


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
def _reset_fills(dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE fills, order_intents CASCADE")
    yield


def _add_fill(
    db_url: str, fill_id: str, client_order_id: str, account_id: str, fee: str, filled_at: datetime
) -> None:
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            """INSERT INTO order_intents (
                 client_order_id, account_id, environment, venue, base, quote, side, kind,
                 quantity, limit_price, decision_id, idempotency_key, risk_assessment_id,
                 config_versions, created_at, expires_at, status
               ) VALUES (
                 %s, %s, 'PAPER', 'kraken', 'BTC', 'USD', 'BUY', 'MARKET', 0.005,
                 NULL, 'decision-1', %s, 'risk-1', '{}'::jsonb,
                 NOW(), NOW() + interval '1 hour', 'FILLED'
               )""",
            (client_order_id, account_id, client_order_id),
        )
        connection.execute(
            """INSERT INTO fills (
                 fill_id, client_order_id, account_id, environment, venue, base, quote, side,
                 quantity, price, fee, fee_currency, filled_at
               ) VALUES (
                 %s, %s, %s, 'PAPER', 'kraken', 'BTC', 'USD', 'BUY',
                 0.005, 50000, %s, 'USD', %s
               )""",
            (fill_id, client_order_id, account_id, fee, filled_at),
        )


async def test_sum_fees_since_only_counts_fills_at_or_after_the_window_start(
    settings, dependencies, sessions
) -> None:
    db_url = dependencies[0]
    _add_fill(db_url, "before", "order-before", ACCOUNT_ID, "1.00", NOW - timedelta(hours=1))
    _add_fill(db_url, "at-start", "order-at-start", ACCOUNT_ID, "2.00", NOW)
    _add_fill(db_url, "after", "order-after", ACCOUNT_ID, "3.00", NOW + timedelta(hours=1))

    async with sessions() as session:
        total = await PortfolioRepository(session).sum_fees_since(ACCOUNT_ID, NOW)

    assert total == Decimal("5.00")


async def test_sum_fees_since_only_counts_the_given_account(
    settings, dependencies, sessions
) -> None:
    _add_fill(dependencies[0], "own", "order-own", ACCOUNT_ID, "1.50", NOW)
    _add_fill(dependencies[0], "other", "order-other", "paper:someone-else", "9.00", NOW)

    async with sessions() as session:
        total = await PortfolioRepository(session).sum_fees_since(ACCOUNT_ID, NOW)

    assert total == Decimal("1.50")


async def test_sum_fees_since_with_no_fills_is_zero(settings, dependencies, sessions) -> None:
    async with sessions() as session:
        total = await PortfolioRepository(session).sum_fees_since(ACCOUNT_ID, NOW)

    assert total == Decimal("0")
