from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.regime import Regime, RegimeClassification
from wallybot.domain.strategy import Action, StrategyContext
from wallybot.strategies.trend_following import TrendFollowingStrategy

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


def make_context(regime: Regime, momentum: Decimal, instrument: Instrument = INSTRUMENT):
    features = FeatureVector(
        instrument=instrument,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={"momentum_5": momentum},
    )
    classification = RegimeClassification(
        instrument=instrument, as_of=AS_OF, version=1, regime=regime, reason="test"
    )
    return StrategyContext(
        instrument=instrument, features=features, regime=classification, as_of=AS_OF
    )


def test_trending_up_yields_buy():
    context = make_context(Regime.TRENDING_UP, Decimal("0.2"))
    signal = TrendFollowingStrategy().evaluate(context)
    assert signal.action == Action.BUY
    assert signal.confidence == Decimal("0.2")
    assert signal.strategy_id == "trend_following"


def test_trending_down_yields_sell():
    context = make_context(Regime.TRENDING_DOWN, Decimal("-0.2"))
    signal = TrendFollowingStrategy().evaluate(context)
    assert signal.action == Action.SELL
    assert signal.confidence == Decimal("0.2")


def test_ranging_yields_hold():
    context = make_context(Regime.RANGING, Decimal("0"))
    signal = TrendFollowingStrategy().evaluate(context)
    assert signal.action == Action.HOLD


def test_risk_off_yields_hold():
    context = make_context(Regime.RISK_OFF, Decimal("-0.5"))
    signal = TrendFollowingStrategy().evaluate(context)
    assert signal.action == Action.HOLD


def test_confidence_is_capped_at_one():
    context = make_context(Regime.TRENDING_UP, Decimal("3.0"))
    signal = TrendFollowingStrategy().evaluate(context)
    assert signal.confidence == Decimal("1")


def test_rejects_regime_for_a_different_instrument():
    features = FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={"momentum_5": Decimal("0.1")},
    )
    mismatched_regime = RegimeClassification(
        instrument=OTHER_INSTRUMENT, as_of=AS_OF, version=1, regime=Regime.TRENDING_UP, reason="x"
    )
    context = StrategyContext(
        instrument=INSTRUMENT, features=features, regime=mismatched_regime, as_of=AS_OF
    )
    with pytest.raises(ValueError):
        TrendFollowingStrategy().evaluate(context)


def test_rejects_missing_momentum_feature():
    features = FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={"sma_5": Decimal("1")},
    )
    classification = RegimeClassification(
        instrument=INSTRUMENT, as_of=AS_OF, version=1, regime=Regime.TRENDING_UP, reason="x"
    )
    context = StrategyContext(
        instrument=INSTRUMENT, features=features, regime=classification, as_of=AS_OF
    )
    with pytest.raises(ValueError):
        TrendFollowingStrategy().evaluate(context)
