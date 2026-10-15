"""The scanner: compose the universe filter (Slice 2) and feature engine (Slice 8) into one
use case -- filter, score, rank, select finalists. The first capability in this repo that
orchestrates multiple capability packages, hence wallybot/application/ per ARCHITECTURE.md's
planned layout ("application/ # use cases and transaction orchestration").
"""

from dataclasses import dataclass
from datetime import datetime

from wallybot.domain.market import Candle, Instrument, MarketSnapshot
from wallybot.features.simple import SimpleFeatureEngine
from wallybot.market.universe import UniverseFilterConfig, evaluate_universe
from wallybot.scoring.simple import Score, score_momentum


@dataclass(frozen=True)
class ScanResult:
    finalists: tuple[Score, ...]
    rejected_instrument_ids: tuple[str, ...]
    ranked: tuple[Score, ...] = ()


def scan_universe(
    instruments: list[Instrument],
    candles_by_instrument: dict[str, list[Candle]],
    snapshots_by_instrument: dict[str, MarketSnapshot],
    universe_config: UniverseFilterConfig,
    as_of: datetime,
    feature_window: int,
    max_finalists: int,
) -> ScanResult:
    """`universe_config.min_history_candles` must be >= `feature_window`, or an eligible
    instrument can still have too little history for the feature engine -- that mismatch is a
    caller configuration error and is left to raise loudly rather than being silently skipped.
    """
    if max_finalists < 1:
        raise ValueError("max_finalists must be positive")

    evaluations = evaluate_universe(
        instruments, candles_by_instrument, snapshots_by_instrument, universe_config
    )
    engine = SimpleFeatureEngine()
    scores: list[Score] = []
    rejected: list[str] = []
    for evaluation in evaluations:
        if not evaluation.eligible:
            rejected.append(evaluation.instrument.id)
            continue
        candles = candles_by_instrument[evaluation.instrument.id]
        vector = engine.compute(candles, as_of=as_of, window=feature_window)
        scores.append(score_momentum(vector, feature_window))

    ranked = sorted(scores, key=lambda score: score.value, reverse=True)
    return ScanResult(
        finalists=tuple(ranked[:max_finalists]),
        rejected_instrument_ids=tuple(rejected),
        ranked=tuple(ranked),
    )
