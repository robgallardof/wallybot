from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.strategy import Action, StrategySignal

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


def make_signal(**overrides) -> StrategySignal:
    fields = {
        "instrument": INSTRUMENT,
        "strategy_id": "trend_following",
        "version": 1,
        "action": Action.BUY,
        "confidence": Decimal("0.5"),
        "as_of": AS_OF,
        "reason": "test",
    }
    fields.update(overrides)
    return StrategySignal(**fields)


def test_accepts_valid_signal():
    signal = make_signal()
    assert signal.action == Action.BUY


def test_rejects_missing_strategy_id():
    with pytest.raises(ValueError):
        make_signal(strategy_id="")


def test_rejects_nonpositive_version():
    with pytest.raises(ValueError):
        make_signal(version=0)


def test_rejects_confidence_below_zero():
    with pytest.raises(ValueError):
        make_signal(confidence=Decimal("-0.1"))


def test_rejects_confidence_above_one():
    with pytest.raises(ValueError):
        make_signal(confidence=Decimal("1.1"))


def test_accepts_boundary_confidence_values():
    assert make_signal(confidence=Decimal("0")).confidence == Decimal("0")
    assert make_signal(confidence=Decimal("1")).confidence == Decimal("1")
