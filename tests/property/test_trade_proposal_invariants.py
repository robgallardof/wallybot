from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.trade_proposal import TradeDirection, TradeProposal

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)

directions = st.sampled_from(list(TradeDirection))
entries = st.decimals(
    min_value="100", max_value="200000", places=2, allow_nan=False, allow_infinity=False
)
spreads = st.decimals(
    min_value="1", max_value="50", places=2, allow_nan=False, allow_infinity=False
)


def _build(direction: TradeDirection, entry: Decimal, spread: Decimal) -> TradeProposal:
    if direction == TradeDirection.LONG:
        stop, take_profit = entry - spread, entry + spread
    else:
        stop, take_profit = entry + spread, entry - spread
    return TradeProposal(
        proposal_id="prop-1",
        instrument=INSTRUMENT,
        direction=direction,
        strategy_id="ai-v1",
        confidence=Decimal("0.5"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=entry,
        stop_price=stop if stop > 0 else None,
        take_profit_price=take_profit,
        time_horizon=timedelta(days=1),
        signal_ttl=timedelta(hours=1),
        reasons=("reason",),
        risks=(),
        supporting_signal_ids=(),
        invalidating_conditions=(),
        source_event_ids=(),
        model_id="model",
        prompt_version="v1",
        as_of=AS_OF,
    )


@given(direction=directions, entry=entries, spread=spreads)
def test_correctly_ordered_stop_and_take_profit_always_construct(
    direction: TradeDirection, entry: Decimal, spread: Decimal
) -> None:
    proposal = _build(direction, entry, spread)
    assert proposal.entry_price == entry


@given(direction=directions, entry=entries, spread=spreads)
def test_swapping_stop_and_take_profit_always_fails(
    direction: TradeDirection, entry: Decimal, spread: Decimal
) -> None:
    # Building with the *opposite* direction's convention on the same entry always inverts the
    # correct ordering for `direction`, so this must always raise.
    opposite = TradeDirection.SHORT if direction == TradeDirection.LONG else TradeDirection.LONG
    wrong = _build(opposite, entry, spread)
    with pytest.raises(ValueError):
        TradeProposal(
            proposal_id=wrong.proposal_id,
            instrument=wrong.instrument,
            direction=direction,
            strategy_id=wrong.strategy_id,
            confidence=wrong.confidence,
            suggested_allocation_pct=wrong.suggested_allocation_pct,
            entry_price=wrong.entry_price,
            stop_price=wrong.stop_price,
            take_profit_price=wrong.take_profit_price,
            time_horizon=wrong.time_horizon,
            signal_ttl=wrong.signal_ttl,
            reasons=wrong.reasons,
            risks=wrong.risks,
            supporting_signal_ids=wrong.supporting_signal_ids,
            invalidating_conditions=wrong.invalidating_conditions,
            source_event_ids=wrong.source_event_ids,
            model_id=wrong.model_id,
            prompt_version=wrong.prompt_version,
            as_of=wrong.as_of,
        )
