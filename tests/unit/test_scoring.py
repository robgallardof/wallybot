from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument, MarketType
from wallybot.scoring.simple import score_momentum

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


def make_vector(**values) -> FeatureVector:
    return FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        version=1,
        values=values,
    )


def test_score_momentum_returns_the_feature_value():
    vector = make_vector(momentum_5=Decimal("0.2"), sma_5=Decimal("110"))
    score = score_momentum(vector, window=5)
    assert score.value == Decimal("0.2")
    assert score.instrument_id == INSTRUMENT.id
    assert score.inputs == vector


def test_score_momentum_raises_when_feature_missing():
    vector = make_vector(sma_5=Decimal("110"))
    with pytest.raises(ValueError):
        score_momentum(vector, window=5)
