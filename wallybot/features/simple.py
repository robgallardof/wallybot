"""Transparent, dependency-free indicators.

Begin with vectorized-in-spirit but plain-Python indicators, per ARCHITECTURE.md's Technology
decisions ("begin with transparent vectorized indicators... evaluate TA-Lib/pandas-ta... before
adoption"); NumPy/Pandas/TA-Lib are deferred to the research extra until a real capability needs
them.
"""

from datetime import datetime
from decimal import Decimal

from wallybot.domain.features import FeatureVector, LookaheadError
from wallybot.domain.market import Candle

FEATURE_VERSION = 1


class SimpleFeatureEngine:
    """Implements wallybot.domain.features.FeatureEngine (structural, not inherited)."""

    def compute(self, candles: list[Candle], as_of: datetime, window: int) -> FeatureVector:
        if window < 1:
            raise ValueError("window must be positive")
        if not candles:
            raise ValueError("candles must not be empty")

        instrument = candles[0].instrument
        timeframe = candles[0].timeframe
        for candle in candles:
            if candle.instrument != instrument:
                raise ValueError("all candles must share the same instrument")
            if candle.timeframe != timeframe:
                raise ValueError("all candles must share the same timeframe")
            if candle.close_time > as_of:
                raise LookaheadError(
                    f"candle closing at {candle.close_time} is after as_of {as_of}"
                )

        ordered = sorted(candles, key=lambda c: c.open_time)
        window_candles = ordered[-window:]
        if len(window_candles) < window:
            raise ValueError(f"need at least {window} candles, got {len(window_candles)}")

        closes = [c.close for c in window_candles]
        sma = sum(closes, Decimal(0)) / len(closes)
        momentum = (closes[-1] - closes[0]) / closes[0]

        return FeatureVector(
            instrument=instrument,
            timeframe=timeframe,
            as_of=as_of,
            version=FEATURE_VERSION,
            values={f"sma_{window}": sma, f"momentum_{window}": momentum},
        )
