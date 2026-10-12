"""Approved AI proposals are revalidated before, at most, one PAPER order exists (ADR-017)."""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.application.execution_service import ExecutionService
from wallybot.application.ledger_postings import build_initial_funding_transaction
from wallybot.application.proposal_execution import (
    PaperAiExecution,
    ProposalExecutionStatus,
    execute_approved_proposal,
)
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType
from wallybot.domain.order import OrderStatus
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.models import OrderIntentRow, ShadowDecisionRow, TradeProposalRow
from wallybot.infrastructure.unit_of_work import unit_of_work

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 2, tzinfo=UTC)
ACCOUNT = "paper-ai:test-operator"
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
    def now(self) -> datetime:
        return NOW


class SequentialIdGenerator:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"proposal-order-{self.counter}"


class ControlledProvider:
    def __init__(self, now: datetime = NOW) -> None:
        closes = [Decimal(50000 + i * 100) for i in range(20)]
        self.candles = []
        for i, close in enumerate(closes):
            open_time = now - timedelta(hours=20 - i)
            self.candles.append(
                Candle(
                    instrument=INSTRUMENT,
                    timeframe="1h",
                    open_time=open_time,
                    close_time=open_time + timedelta(hours=1),
                    open=close,
                    high=close + Decimal("1"),
                    low=close - Decimal("1"),
                    close=close,
                    volume=Decimal("10"),
                    source="test",
                    received_at=open_time + timedelta(hours=1),
                )
            )
        self.snapshot = MarketSnapshot(
            instrument=INSTRUMENT,
            bid=closes[-1] - Decimal("5"),
            ask=closes[-1] + Decimal("5"),
            timestamp=now,
            source="test",
        )

    async def discover_instruments(self) -> list[Instrument]:
        return [INSTRUMENT]

    async def fetch_candles(self, instrument, timeframe, since, limit) -> list[Candle]:
        return [c for c in self.candles if c.open_time >= since][:limit]

    async def fetch_snapshot(self, instrument) -> MarketSnapshot:
        return self.snapshot


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_tables(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE equity_snapshots, breakers, ledger_postings, ledger_transactions, "
            "ledger_accounts, fills, order_transitions, order_intents, shadow_decisions, "
            "trade_proposals CASCADE"
        )
    yield


def _row(direction: str = "LONG", as_of: datetime = NOW - timedelta(minutes=1)):
    return TradeProposalRow(
        proposal_id=f"proposal-{direction.lower()}",
        venue="test",
        base="BTC",
        quote="USD",
        direction=direction,
        strategy_id="ai-consensus",
        confidence=Decimal("0.8"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=Decimal("51900"),
        stop_price=None,
        take_profit_price=None,
        time_horizon_seconds=Decimal("86400"),
        signal_ttl_seconds=Decimal("3600"),
        reasons=["analysts agree"],
        risks=["volatility"],
        supporting_signal_ids=[],
        invalidating_conditions=[],
        source_event_ids=[],
        model_id="consensus:codex+claude",
        prompt_version="consensus/v1",
        as_of=as_of,
        owner_id=None,
        decision_status="APPROVED",
    )


async def _prepare(sessions, row: TradeProposalRow) -> tuple[PaperAiExecution, ControlledProvider]:
    async with sessions.begin() as db:
        db.add(row)
    async with unit_of_work(sessions) as uow:
        await uow.save_ledger_transaction(
            build_initial_funding_transaction(ACCOUNT, "USD", Decimal("100000"), "fund-1", NOW)
        )
    provider = ControlledProvider()
    gateway = FakeExchange(clock=FixedClock(), market_data=provider)
    execution = ExecutionService(gateway=gateway, sessions=sessions, clock=FixedClock())
    paper = PaperAiExecution(
        gateway=gateway,
        execution=execution,
        reconciliation=ReconciliationService(execution=execution, sessions=sessions),
    )
    return paper, provider


async def test_an_approved_buy_is_revalidated_then_filled_once_on_the_ai_account(sessions):
    row = _row()
    paper, provider = await _prepare(sessions, row)

    result = await execute_approved_proposal(
        sessions, provider, paper, SequentialIdGenerator(), row, ACCOUNT, NOW
    )

    assert result.status == OrderStatus.FILLED.value
    assert result.client_order_id is not None
    async with sessions() as db:
        orders = (await db.scalars(select(OrderIntentRow))).all()
        evidence = (await db.scalars(select(ShadowDecisionRow))).all()
    assert len(orders) == 1
    assert orders[0].account_id == ACCOUNT
    assert orders[0].side == "BUY"
    assert orders[0].idempotency_key == "proposal:proposal-long"
    assert len(evidence) == 1


async def test_an_expired_proposal_never_reaches_the_gateway(sessions):
    row = _row(as_of=NOW - timedelta(hours=2))
    paper, provider = await _prepare(sessions, row)

    result = await execute_approved_proposal(
        sessions, provider, paper, SequentialIdGenerator(), row, ACCOUNT, NOW
    )

    assert result.status == ProposalExecutionStatus.EXPIRED
    assert result.client_order_id is None
    async with sessions() as db:
        assert (await db.scalars(select(OrderIntentRow))).all() == []


async def test_a_sell_without_a_held_position_is_blocked_not_shorted(sessions):
    row = _row(direction="SHORT")
    paper, provider = await _prepare(sessions, row)

    result = await execute_approved_proposal(
        sessions, provider, paper, SequentialIdGenerator(), row, ACCOUNT, NOW
    )

    assert result.status == ProposalExecutionStatus.BLOCKED
    assert result.client_order_id is None
    assert result.reasons
    async with sessions() as db:
        assert (await db.scalars(select(OrderIntentRow))).all() == []


async def test_a_separately_approved_sell_reduces_the_existing_paper_position(sessions):
    buy = _row()
    paper, provider = await _prepare(sessions, buy)
    ids = SequentialIdGenerator()
    bought = await execute_approved_proposal(sessions, provider, paper, ids, buy, ACCOUNT, NOW)
    assert bought.status == "FILLED"
    sell = _row(direction="SHORT")
    sell.suggested_allocation_pct = Decimal("1")
    async with sessions.begin() as db:
        db.add(sell)
    sold = await execute_approved_proposal(sessions, provider, paper, ids, sell, ACCOUNT, NOW)
    assert sold.status == "FILLED", sold.reasons
    async with sessions() as db:
        orders = (await db.scalars(select(OrderIntentRow).order_by(OrderIntentRow.side))).all()
    assert len(orders) == 2
    assert orders[0].side == "BUY"
    assert orders[1].side == "SELL"
    assert orders[1].quantity <= orders[0].quantity
