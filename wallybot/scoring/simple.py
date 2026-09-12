"""Deterministic, versioned scoring. No ML, no randomness -- a score must be reproducible from
the same feature vector every time, per ARCHITECTURE.md's "Versioned scoring ranks finalists."
"""

from dataclasses import dataclass
from decimal import Decimal

from wallybot.domain.features import FeatureVector

SCORING_VERSION = 1


@dataclass(frozen=True)
class Score:
    instrument_id: str
    version: int
    value: Decimal
    inputs: FeatureVector


def score_momentum(vector: FeatureVector, window: int) -> Score:
    """Higher recent momentum ranks higher. The simplest possible starting score."""
    key = f"momentum_{window}"
    if key not in vector.values:
        raise ValueError(f"feature vector is missing '{key}'")
    return Score(
        instrument_id=vector.instrument.id,
        version=SCORING_VERSION,
        value=vector.values[key],
        inputs=vector,
    )
