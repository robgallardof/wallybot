"""Composes market discovery, per-instrument data quality, universe filtering and scoring into
one view an API route can serve to a dashboard.

This is the first place any of Phase 2/3's domain and capability code is actually wired to
something a user can see -- everything before this was pure, tested, but silent. Matches the
product's own stated priority: "connect data -> quality -> scanner -> API -> markets screen."
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.clock import Clock
from wallybot.domain.market import TIMEFRAME_DURATIONS, Instrument, MarketDataProvider
from wallybot.domain.quality import QualityReport
from wallybot.features.simple import SimpleFeatureEngine
from wallybot.market.universe import UniverseFilterConfig, evaluate_universe
from wallybot.scoring.simple import score_momentum

DEFAULT_MAX_CONCURRENCY = 6


@dataclass(frozen=True)
class MarketOverviewRow:
    instrument: Instrument
    bid: Decimal
    ask: Decimal
    quality: QualityReport
    eligible: bool
    reasons: tuple[str, ...]
    score: Decimal | None
    rank: int | None


@dataclass(frozen=True)
class MarketOverview:
    as_of: datetime
    rows: tuple[MarketOverviewRow, ...]


async def build_market_overview(
    provider: MarketDataProvider,
    clock: Clock,
    timeframe: str,
    history_candles: int,
    universe_config: UniverseFilterConfig,
    quality_policy: QualityPolicy,
    feature_window: int,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> MarketOverview:
    now = clock.now()
    since = now - TIMEFRAME_DURATIONS[timeframe] * history_candles
    instruments = await provider.discover_instruments()

    candles_by_id: dict[str, list] = {}
    snapshots_by_id = {}
    quality_by_id = {}
    failed_ids: set[str] = set()
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch(instrument: Instrument) -> None:
        async with semaphore:
            try:
                candles = await provider.fetch_candles(
                    instrument, timeframe, since, history_candles
                )
                snapshot = await provider.fetch_snapshot(instrument)
            except Exception:
                # One instrument's provider hiccup never takes down the whole overview -- it's
                # simply excluded, same "a fetch failure is never shown as a valid quote"
                # principle every other data path in this codebase already follows.
                failed_ids.add(instrument.id)
                return
        candles_by_id[instrument.id] = candles
        snapshots_by_id[instrument.id] = snapshot
        quality_by_id[instrument.id] = evaluate_series_quality(candles, quality_policy, now)

    await asyncio.gather(*(fetch(instrument) for instrument in instruments))
    instruments = [instrument for instrument in instruments if instrument.id not in failed_ids]

    evaluations = {
        e.instrument.id: e
        for e in evaluate_universe(instruments, candles_by_id, snapshots_by_id, universe_config)
    }

    engine = SimpleFeatureEngine()
    scores: dict[str, Decimal] = {}
    for instrument in instruments:
        evaluation = evaluations[instrument.id]
        candles = candles_by_id[instrument.id]
        if not evaluation.eligible or len(candles) < feature_window:
            continue
        vector = engine.compute(candles, now, feature_window)
        scores[instrument.id] = score_momentum(vector, feature_window).value

    ranked_ids = [
        instrument_id
        for instrument_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)
    ]
    rank_by_id = {instrument_id: index + 1 for index, instrument_id in enumerate(ranked_ids)}

    rows = tuple(
        MarketOverviewRow(
            instrument=instrument,
            bid=snapshots_by_id[instrument.id].bid,
            ask=snapshots_by_id[instrument.id].ask,
            quality=quality_by_id[instrument.id],
            eligible=evaluations[instrument.id].eligible,
            reasons=evaluations[instrument.id].reasons,
            score=scores.get(instrument.id),
            rank=rank_by_id.get(instrument.id),
        )
        for instrument in instruments
    )
    return MarketOverview(as_of=now, rows=rows)
