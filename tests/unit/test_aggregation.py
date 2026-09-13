from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.strategy import Action

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def make_aggregated(**overrides) -> AggregatedSignal:
    fields = {
        "instrument": INSTRUMENT,
        "action": Action.BUY,
        "confidence": Decimal("0.5"),
        "version": 1,
        "as_of": AS_OF,
        "contributing_signals": (),
        "reason": "test",
    }
    fields.update(overrides)
    return AggregatedSignal(**fields)


def test_accepts_valid_aggregated_signal():
    assert make_aggregated().action == Action.BUY


def test_rejects_nonpositive_version():
    with pytest.raises(ValueError):
        make_aggregated(version=0)


def test_rejects_confidence_out_of_bounds():
    with pytest.raises(ValueError):
        make_aggregated(confidence=Decimal("1.5"))
