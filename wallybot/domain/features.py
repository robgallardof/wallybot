from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from wallybot.domain.market import Candle, Instrument


class LookaheadError(ValueError):
    """A candle closing after `as_of` would leak into the computation.

    Raised rather than silently dropped, so a caller's bug surfaces immediately instead of
    quietly producing a feature that peeked at the future -- per ARCHITECTURE.md's
    FeatureEngine contract: "Versioned features from validated as-of data; no future
    observations."
    """


@dataclass(frozen=True)
class FeatureVector:
    instrument: Instrument
    timeframe: str
    as_of: datetime
    version: int
    values: Mapping[str, Decimal]


class FeatureEngine(Protocol):
    """Computes versioned features from as-of data only. Never trading credentials, never I/O."""

    def compute(self, candles: list[Candle], as_of: datetime, window: int) -> FeatureVector: ...
