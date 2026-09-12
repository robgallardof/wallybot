from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.regime import Regime, classify_regime

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
RISK_OFF_THRESHOLD = Decimal("0.1")


def make_vector(momentum: Decimal, window: int = 5) -> FeatureVector:
    return FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={f"momentum_{window}": momentum},
    )


def test_positive_momentum_is_trending_up():
    classification = classify_regime(make_vector(Decimal("0.05")), RISK_OFF_THRESHOLD)
    assert classification.regime == Regime.TRENDING_UP
    assert classification.instrument == INSTRUMENT
    assert classification.as_of == AS_OF
    assert classification.version == 1


def test_negative_momentum_above_threshold_is_trending_down():
    classification = classify_regime(make_vector(Decimal("-0.05")), RISK_OFF_THRESHOLD)
    assert classification.regime == Regime.TRENDING_DOWN


def test_zero_momentum_is_ranging():
    classification = classify_regime(make_vector(Decimal("0")), RISK_OFF_THRESHOLD)
    assert classification.regime == Regime.RANGING


def test_momentum_at_exactly_the_threshold_is_risk_off():
    classification = classify_regime(make_vector(-RISK_OFF_THRESHOLD), RISK_OFF_THRESHOLD)
    assert classification.regime == Regime.RISK_OFF


def test_momentum_beyond_the_threshold_is_risk_off():
    classification = classify_regime(make_vector(Decimal("-0.5")), RISK_OFF_THRESHOLD)
    assert classification.regime == Regime.RISK_OFF


def test_rejects_vector_without_a_momentum_feature():
    vector = FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={"sma_5": Decimal("100")},
    )
    with pytest.raises(ValueError):
        classify_regime(vector, RISK_OFF_THRESHOLD)


def test_rejects_nonpositive_threshold():
    with pytest.raises(ValueError):
        classify_regime(make_vector(Decimal("0.05")), Decimal("0"))
