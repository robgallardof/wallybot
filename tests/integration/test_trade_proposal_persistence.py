import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal
from wallybot.infrastructure.models import TradeProposalRow
from wallybot.infrastructure.trade_proposal_repository import TradeProposalRepository

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


AS_OF = datetime(2026, 1, 10, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="kraken",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


def make_proposal(proposal_id: str) -> TradeProposal:
    return TradeProposal(
        proposal_id=proposal_id,
        instrument=INSTRUMENT,
        direction=TradeDirection.LONG,
        strategy_id="ai-trend-v1",
        confidence=Decimal("0.72"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=Decimal("50000"),
        stop_price=Decimal("48000"),
        take_profit_price=Decimal("55000"),
        time_horizon=timedelta(days=3),
        signal_ttl=timedelta(hours=1),
        reasons=("Momentum confirms uptrend",),
        risks=("Regime could reverse",),
        supporting_signal_ids=("signal-1", "signal-2"),
        invalidating_conditions=("Close below 47000",),
        source_event_ids=("event-1",),
        model_id="claude-sonnet-5",
        prompt_version="v1",
        as_of=AS_OF,
    )


@pytest.fixture
def sessions(settings, dependencies):
    engine = create_async_engine(dependencies[0])
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker


@pytest.fixture(autouse=True)
def _reset_trade_proposals_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE trade_proposals CASCADE")
    yield


async def test_a_saved_proposal_persists_every_field(sessions) -> None:
    proposal = make_proposal("prop-1")
    async with sessions.begin() as session:
        await TradeProposalRepository(session).save(proposal)

    async with sessions() as session:
        row = (
            await session.execute(
                select(TradeProposalRow).where(TradeProposalRow.proposal_id == "prop-1")
            )
        ).scalar_one()

    assert row.venue == "kraken"
    assert row.base == "BTC"
    assert row.quote == "USD"
    assert row.direction == "LONG"
    assert row.strategy_id == "ai-trend-v1"
    assert row.confidence == proposal.confidence
    assert row.suggested_allocation_pct == proposal.suggested_allocation_pct
    assert row.entry_price == proposal.entry_price
    assert row.stop_price == proposal.stop_price
    assert row.take_profit_price == proposal.take_profit_price
    assert row.reasons == list(proposal.reasons)
    assert row.risks == list(proposal.risks)
    assert row.supporting_signal_ids == list(proposal.supporting_signal_ids)
    assert row.invalidating_conditions == list(proposal.invalidating_conditions)
    assert row.source_event_ids == list(proposal.source_event_ids)
    assert row.model_id == "claude-sonnet-5"
    assert row.prompt_version == "v1"
    assert row.as_of == AS_OF


async def test_two_proposals_for_the_same_instrument_both_persist(sessions) -> None:
    first = make_proposal("prop-1")
    second = make_proposal("prop-2")
    async with sessions.begin() as session:
        repo = TradeProposalRepository(session)
        await repo.save(first)
        await repo.save(second)

    async with sessions() as session:
        rows = (await session.execute(select(TradeProposalRow))).scalars().all()

    assert {row.proposal_id for row in rows} == {"prop-1", "prop-2"}
