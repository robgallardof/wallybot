"""Deterministic, versioned regime classification from an existing FeatureVector (Slice 8).

Per ARCHITECTURE.md's decision flow ("Regime classification and strategies produce signals") and
RISK.md ("Neutral and risk-off regimes may reduce ceilings"). Only the classification rule lives
here; nothing yet consumes a regime to actually change a risk ceiling -- that arrives with
RiskEngine, a deliberately separate, later piece of work.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument

REGIME_VERSION = 1


class Regime(StrEnum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    RISK_OFF = "RISK_OFF"


@dataclass(frozen=True)
class RegimeClassification:
    instrument: Instrument
    as_of: datetime
    version: int
    regime: Regime
    reason: str


def classify_regime(vector: FeatureVector, risk_off_threshold: Decimal) -> RegimeClassification:
    if risk_off_threshold <= 0:
        raise ValueError("risk_off_threshold must be positive")
    momentum_key = next((key for key in vector.values if key.startswith("momentum_")), None)
    if momentum_key is None:
        raise ValueError("feature vector must include a momentum_<window> value")
    momentum = vector.values[momentum_key]

    if momentum <= -risk_off_threshold:
        regime = Regime.RISK_OFF
        reason = f"{momentum_key}={momentum} at or below risk-off threshold -{risk_off_threshold}"
    elif momentum > 0:
        regime = Regime.TRENDING_UP
        reason = f"{momentum_key}={momentum} positive"
    elif momentum < 0:
        regime = Regime.TRENDING_DOWN
        reason = f"{momentum_key}={momentum} negative, above risk-off threshold"
    else:
        regime = Regime.RANGING
        reason = f"{momentum_key}=0"

    return RegimeClassification(
        instrument=vector.instrument,
        as_of=vector.as_of,
        version=REGIME_VERSION,
        regime=regime,
        reason=reason,
    )
