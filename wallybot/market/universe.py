from dataclasses import dataclass
from decimal import Decimal

from wallybot.domain.market import Candle, Instrument, MarketSnapshot
from wallybot.domain.quality import QualityReport, QualityStatus


@dataclass(frozen=True)
class UniverseFilterConfig:
    """Thresholds are versioned configuration per DATA.md, never a silent code change."""

    version: int
    min_history_candles: int
    min_average_quote_volume: Decimal
    max_spread_ratio: Decimal

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.min_history_candles < 1:
            raise ValueError("min_history_candles must be positive")
        if self.min_average_quote_volume < 0:
            raise ValueError("min_average_quote_volume must be nonnegative")
        if self.max_spread_ratio <= 0:
            raise ValueError("max_spread_ratio must be positive")


@dataclass(frozen=True)
class UniverseEvaluation:
    instrument: Instrument
    eligible: bool
    reasons: tuple[str, ...]


def evaluate_instrument(
    instrument: Instrument,
    candles: list[Candle],
    snapshot: MarketSnapshot | None,
    config: UniverseFilterConfig,
    quality: QualityReport | None = None,
) -> UniverseEvaluation:
    """`quality` is optional -- `wallybot.application.decision_pipeline` already excludes
    FAILURE-quality instruments from the candidate list it passes in here, so it never needs to
    pass one. A caller that hasn't pre-filtered (e.g. `market_overview.py`'s read-only Markets
    view) passes its own per-instrument `QualityReport` instead of duplicating this check --
    ARCHITECTURE.md: "quality checks gate features," not just the live trading path.
    """
    reasons: list[str] = []
    if len(candles) < config.min_history_candles:
        reasons.append("insufficient_history")
    average_quote_volume = (
        sum((candle.volume * candle.close for candle in candles), Decimal(0)) / len(candles)
        if candles
        else Decimal(0)
    )
    if average_quote_volume < config.min_average_quote_volume:
        reasons.append("illiquid")
    if snapshot is None:
        reasons.append("unavailable")
    elif snapshot.spread_ratio > config.max_spread_ratio:
        reasons.append("wide_spread")
    if quality is not None and quality.status == QualityStatus.FAILURE:
        reasons.append("data_quality_failure")
    return UniverseEvaluation(instrument=instrument, eligible=not reasons, reasons=tuple(reasons))


def evaluate_universe(
    instruments: list[Instrument],
    candles_by_instrument: dict[str, list[Candle]],
    snapshots_by_instrument: dict[str, MarketSnapshot],
    config: UniverseFilterConfig,
    quality_by_instrument: dict[str, QualityReport] | None = None,
) -> list[UniverseEvaluation]:
    return [
        evaluate_instrument(
            instrument,
            candles_by_instrument.get(instrument.id, []),
            snapshots_by_instrument.get(instrument.id),
            config,
            quality_by_instrument.get(instrument.id) if quality_by_instrument else None,
        )
        for instrument in instruments
    ]


def eligible_instruments(evaluations: list[UniverseEvaluation]) -> list[Instrument]:
    return [evaluation.instrument for evaluation in evaluations if evaluation.eligible]
