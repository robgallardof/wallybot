import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.smart_money_cluster import SmartMoneyClusterSignal
from wallybot.domain.wallet_activity import OnChainActionType
from wallybot.infrastructure.smart_money_cluster_repository import SmartMoneyClusterRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


NOW = datetime(2026, 1, 10, tzinfo=UTC)


def make_signal(window_end: datetime, token: str = "BONK") -> SmartMoneyClusterSignal:
    return SmartMoneyClusterSignal(
        token=token,
        chain="solana",
        action=OnChainActionType.BUY,
        window_start=window_end - timedelta(minutes=20),
        window_end=window_end,
        wallet_ids=("solana:a", "solana:b", "solana:c"),
        independent_wallet_count=3,
        total_value_usd=Decimal("30000"),
        average_entry_price=Decimal("10"),
        independence_score=Decimal("1"),
        confidence=Decimal("0.5"),
        reasons=(
            "3 independent wallet(s) BUY BONK within 0:30:00",
            "not evaluated: liquidity_change",
        ),
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_smart_money_cluster_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE smart_money_cluster_signals CASCADE")
    yield


async def test_a_saved_signal_round_trips(sessions) -> None:
    signal = make_signal(NOW)
    async with sessions.begin() as session:
        await SmartMoneyClusterRepository(session).save(signal)

    async with sessions() as session:
        latest = await SmartMoneyClusterRepository(session).latest()
    assert len(latest) == 1
    assert latest[0].wallet_ids == signal.wallet_ids
    assert latest[0].total_value_usd == signal.total_value_usd
    assert latest[0].reasons == signal.reasons


async def test_saving_a_second_signal_never_overwrites_the_first(sessions) -> None:
    first = make_signal(NOW - timedelta(hours=1))
    second = make_signal(NOW)
    async with sessions.begin() as session:
        repo = SmartMoneyClusterRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        history = await SmartMoneyClusterRepository(session).history_for_token("solana", "BONK")

    assert len(history) == 2
    assert history[0].window_end == first.window_end
    assert history[1].window_end == second.window_end


async def test_history_for_token_only_returns_matching_chain_and_token(sessions) -> None:
    bonk_signal = make_signal(NOW, token="BONK")
    wif_signal = make_signal(NOW, token="WIF")
    async with sessions.begin() as session:
        repo = SmartMoneyClusterRepository(session)
        await repo.save(bonk_signal)
        await repo.save(wif_signal)

    async with sessions() as session:
        history = await SmartMoneyClusterRepository(session).history_for_token("solana", "BONK")

    assert len(history) == 1
    assert history[0].token == "BONK"
