from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

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


def make_proposal(**overrides: object) -> TradeProposal:
    fields: dict[str, object] = {
        "proposal_id": "prop-1",
        "instrument": INSTRUMENT,
        "direction": TradeDirection.LONG,
        "strategy_id": "ai-trend-v1",
        "confidence": Decimal("0.7"),
        "suggested_allocation_pct": Decimal("0.05"),
        "entry_price": Decimal("50000"),
        "stop_price": Decimal("48000"),
        "take_profit_price": Decimal("55000"),
        "time_horizon": timedelta(days=3),
        "signal_ttl": timedelta(hours=1),
        "reasons": ("Momentum confirms uptrend",),
        "risks": ("Regime could reverse",),
        "supporting_signal_ids": ("signal-1",),
        "invalidating_conditions": ("Close below 47000",),
        "source_event_ids": ("event-1",),
        "model_id": "claude-sonnet-5",
        "prompt_version": "v1",
        "as_of": AS_OF,
    }
    fields.update(overrides)
    return TradeProposal(**fields)  # type: ignore[arg-type]


def test_a_valid_long_proposal_constructs() -> None:
    proposal = make_proposal()
    assert proposal.direction == TradeDirection.LONG


def test_a_valid_short_proposal_constructs() -> None:
    proposal = make_proposal(
        direction=TradeDirection.SHORT,
        stop_price=Decimal("52000"),
        take_profit_price=Decimal("45000"),
    )
    assert proposal.direction == TradeDirection.SHORT


def test_a_proposal_without_stop_or_take_profit_constructs() -> None:
    proposal = make_proposal(stop_price=None, take_profit_price=None)
    assert proposal.stop_price is None
    assert proposal.take_profit_price is None


@pytest.mark.parametrize("field", ["proposal_id", "strategy_id", "model_id", "prompt_version"])
def test_required_identifier_fields_reject_empty_string(field: str) -> None:
    with pytest.raises(ValueError, match="required"):
        make_proposal(**{field: ""})


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="confidence"):
        make_proposal(confidence=Decimal("1.1"))


def test_zero_allocation_rejected() -> None:
    with pytest.raises(ValueError, match="suggested_allocation_pct"):
        make_proposal(suggested_allocation_pct=Decimal(0))


def test_allocation_above_one_rejected() -> None:
    with pytest.raises(ValueError, match="suggested_allocation_pct"):
        make_proposal(suggested_allocation_pct=Decimal("1.5"))


def test_nonpositive_entry_price_rejected() -> None:
    with pytest.raises(ValueError, match="entry_price"):
        make_proposal(entry_price=Decimal(0))


def test_long_stop_above_entry_rejected() -> None:
    with pytest.raises(ValueError, match="LONG stop_price"):
        make_proposal(stop_price=Decimal("51000"))


def test_long_take_profit_below_entry_rejected() -> None:
    with pytest.raises(ValueError, match="LONG take_profit_price"):
        make_proposal(take_profit_price=Decimal("49000"))


def test_short_stop_below_entry_rejected() -> None:
    with pytest.raises(ValueError, match="SHORT stop_price"):
        make_proposal(
            direction=TradeDirection.SHORT,
            stop_price=Decimal("49000"),
            take_profit_price=Decimal("45000"),
        )


def test_short_take_profit_above_entry_rejected() -> None:
    with pytest.raises(ValueError, match="SHORT take_profit_price"):
        make_proposal(
            direction=TradeDirection.SHORT,
            stop_price=Decimal("52000"),
            take_profit_price=Decimal("51000"),
        )


def test_nonpositive_time_horizon_rejected() -> None:
    with pytest.raises(ValueError, match="time_horizon"):
        make_proposal(time_horizon=timedelta(0))


def test_nonpositive_signal_ttl_rejected() -> None:
    with pytest.raises(ValueError, match="signal_ttl"):
        make_proposal(signal_ttl=timedelta(0))


def test_empty_reasons_rejected() -> None:
    with pytest.raises(ValueError, match="reasons"):
        make_proposal(reasons=())


def test_naive_as_of_rejected() -> None:
    with pytest.raises(ValueError, match="as_of"):
        make_proposal(as_of=datetime(2026, 1, 1))
