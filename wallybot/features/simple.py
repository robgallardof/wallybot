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

# Version 2 adds volatility, range and volume features. Persisted experiments retain this value,
# so a future change cannot silently masquerade as the same feature set during a replay.
FEATURE_VERSION = 2


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
        returns = [
            (current - previous) / previous
            for previous, current in zip(closes[:-1], closes[1:], strict=True)
        ]
        # Population volatility is intentional: this window is the entire available observation
        # set at `as_of`, not a sample being used to estimate an unseen population. A one-candle
        # window has no return observations, so its volatility is honestly zero rather than NaN.
        realized_volatility = (
            (sum((value * value for value in returns), Decimal(0)) / len(returns)).sqrt()
            if returns
            else Decimal(0)
        )
        true_ranges = []
        previous_close: Decimal | None = None
        for candle in window_candles:
            candidates = [candle.high - candle.low]
            if previous_close is not None:
                candidates.extend(
                    (abs(candle.high - previous_close), abs(candle.low - previous_close))
                )
            true_ranges.append(max(candidates))
            previous_close = candle.close
        atr = sum(true_ranges, Decimal(0)) / len(true_ranges)
        average_volume = sum((candle.volume for candle in window_candles), Decimal(0)) / len(
            window_candles
        )
        relative_volume = (
            window_candles[-1].volume / average_volume if average_volume else Decimal(0)
        )
        average_quote_volume = sum(
            (candle.volume * candle.close for candle in window_candles), Decimal(0)
        ) / len(window_candles)

        return FeatureVector(
            instrument=instrument,
            timeframe=timeframe,
            as_of=as_of,
            version=FEATURE_VERSION,
            values={
                f"sma_{window}": sma,
                f"momentum_{window}": momentum,
                f"realized_volatility_{window}": realized_volatility,
                f"atr_{window}": atr,
                f"relative_volume_{window}": relative_volume,
                f"average_quote_volume_{window}": average_quote_volume,
            },
        )
