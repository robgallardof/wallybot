"""Composes market discovery, per-instrument data quality, universe filtering and scoring into
one view an API route can serve to a dashboard.

This is the first place any of Phase 2/3's domain and capability code is actually wired to
something a user can see -- everything before this was pure, tested, but silent. Matches the
product's own stated priority: "connect data -> quality -> scanner -> API -> markets screen."
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.clock import Clock
from wallybot.domain.market import TIMEFRAME_DURATIONS, Candle, Instrument, MarketDataProvider
from wallybot.domain.quality import QualityReport
from wallybot.features.simple import SimpleFeatureEngine
from wallybot.infrastructure.market_cache import MarketCache
from wallybot.market.universe import UniverseFilterConfig, evaluate_instrument, evaluate_universe
from wallybot.scoring.simple import score_momentum

DEFAULT_MAX_CONCURRENCY = 6
# ADR-003: a disposable hot-tier accelerator, not a freshness guarantee -- candles (which quality
# actually gates on) are always fetched fresh regardless; only the lightweight bid/ask snapshot is
# ever served from cache, and only for this short a window.
DEFAULT_SNAPSHOT_CACHE_TTL = timedelta(seconds=30)


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
    cache: MarketCache | None = None,
    cache_ttl: timedelta = DEFAULT_SNAPSHOT_CACHE_TTL,
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
                snapshot = await cache.get_snapshot(instrument) if cache is not None else None
                if snapshot is None:
                    snapshot = await provider.fetch_snapshot(instrument)
                    if cache is not None:
                        await cache.set_snapshot(snapshot, ttl=cache_ttl)
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
        for e in evaluate_universe(
            instruments, candles_by_id, snapshots_by_id, universe_config, quality_by_id
        )
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


@dataclass(frozen=True)
class InstrumentDetail:
    instrument: Instrument
    as_of: datetime
    bid: Decimal
    ask: Decimal
    candles: tuple[Candle, ...]
    quality: QualityReport
    eligible: bool
    reasons: tuple[str, ...]


async def build_instrument_detail(
    provider: MarketDataProvider,
    clock: Clock,
    instrument_id: str,
    timeframe: str,
    history_candles: int,
    universe_config: UniverseFilterConfig,
    quality_policy: QualityPolicy,
) -> InstrumentDetail | None:
    """Candles/volume/quality for one instrument, e.g. for a detail/chart view -- `None` when
    `instrument_id` doesn't match anything the provider currently discovers, so the caller can
    honestly return 404 rather than a fabricated empty detail. Same quality/eligibility gate
    `build_market_overview` applies, just for a single instrument instead of the whole universe.
    """
    now = clock.now()
    since = now - TIMEFRAME_DURATIONS[timeframe] * history_candles
    instruments = await provider.discover_instruments()
    instrument = next((i for i in instruments if i.id == instrument_id), None)
    if instrument is None:
        return None

    candles = await provider.fetch_candles(instrument, timeframe, since, history_candles)
    snapshot = await provider.fetch_snapshot(instrument)
    quality = evaluate_series_quality(candles, quality_policy, now)
    evaluation = evaluate_instrument(instrument, candles, snapshot, universe_config, quality)

    return InstrumentDetail(
        instrument=instrument,
        as_of=now,
        bid=snapshot.bid,
        ask=snapshot.ask,
        candles=tuple(candles),
        quality=quality,
        eligible=evaluation.eligible,
        reasons=evaluation.reasons,
    )
