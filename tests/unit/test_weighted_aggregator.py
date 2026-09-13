from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.strategy import Action, StrategySignal
from wallybot.signals.weighted_aggregator import WeightedSignalAggregator

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
OTHER_INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="ETH",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.001"),
    min_quantity=Decimal("0.001"),
)
AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def make_signal(strategy_id: str, action: Action, confidence: str, instrument=INSTRUMENT):
    return StrategySignal(
        instrument=instrument,
        strategy_id=strategy_id,
        version=1,
        action=action,
        confidence=Decimal(confidence),
        as_of=AS_OF,
        reason="test",
    )


def make_aggregator(min_quorum: int = 2, min_agreement_ratio: str = "0.3"):
    return WeightedSignalAggregator(
        weights={"a": Decimal("1"), "b": Decimal("1"), "c": Decimal("3")},
        min_quorum=min_quorum,
        min_agreement_ratio=Decimal(min_agreement_ratio),
    )


def test_full_agreement_yields_buy_with_full_confidence():
    signals = [
        make_signal("a", Action.BUY, "1"),
        make_signal("b", Action.BUY, "1"),
    ]
    result = make_aggregator().aggregate(signals, AS_OF)
    assert result.action == Action.BUY
    assert result.confidence == Decimal("1")


def test_full_disagreement_yields_hold():
    signals = [
        make_signal("a", Action.BUY, "1"),
        make_signal("b", Action.SELL, "1"),
    ]
    result = make_aggregator().aggregate(signals, AS_OF)
    assert result.action == Action.HOLD
    assert result.confidence == Decimal("0")
    assert "agreement" in result.reason


def test_weak_agreement_below_threshold_yields_hold():
    signals = [
        make_signal("a", Action.BUY, "0.6"),
        make_signal("b", Action.SELL, "0.5"),
    ]
    result = make_aggregator(min_agreement_ratio="0.3").aggregate(signals, AS_OF)
    assert result.action == Action.HOLD


def test_strong_weighted_majority_yields_buy():
    signals = [
        make_signal("c", Action.BUY, "1"),  # weight 3
        make_signal("a", Action.SELL, "1"),  # weight 1
    ]
    result = make_aggregator(min_agreement_ratio="0.3").aggregate(signals, AS_OF)
    assert result.action == Action.BUY
    # buy=3, sell=1, net=2, total=4, agreement=0.5
    assert result.confidence == Decimal("0.5")


def test_quorum_not_met_yields_hold():
    signals = [make_signal("a", Action.BUY, "1")]
    result = make_aggregator(min_quorum=2).aggregate(signals, AS_OF)
    assert result.action == Action.HOLD
    assert "quorum" in result.reason


def test_rejects_unconfigured_strategy():
    signals = [
        make_signal("a", Action.BUY, "1"),
        make_signal("unknown", Action.BUY, "1"),
    ]
    with pytest.raises(ValueError):
        make_aggregator().aggregate(signals, AS_OF)


def test_rejects_mismatched_instruments():
    signals = [
        make_signal("a", Action.BUY, "1"),
        make_signal("b", Action.BUY, "1", instrument=OTHER_INSTRUMENT),
    ]
    with pytest.raises(ValueError):
        make_aggregator().aggregate(signals, AS_OF)


def test_rejects_empty_signals():
    with pytest.raises(ValueError):
        make_aggregator().aggregate([], AS_OF)


def test_constructor_rejects_nonpositive_quorum():
    with pytest.raises(ValueError):
        WeightedSignalAggregator(weights={}, min_quorum=0, min_agreement_ratio=Decimal("0.5"))


def test_constructor_rejects_agreement_ratio_out_of_bounds():
    with pytest.raises(ValueError):
        WeightedSignalAggregator(weights={}, min_quorum=1, min_agreement_ratio=Decimal("0"))
    with pytest.raises(ValueError):
        WeightedSignalAggregator(weights={}, min_quorum=1, min_agreement_ratio=Decimal("1.1"))


def test_constructor_rejects_nonpositive_weight():
    with pytest.raises(ValueError):
        WeightedSignalAggregator(
            weights={"a": Decimal("0")}, min_quorum=1, min_agreement_ratio=Decimal("0.5")
        )
