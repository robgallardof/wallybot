"""Closes PENDING.md's "Parquet dataset-ingestion job" gap: nothing in production ever called
`HistoricalStore.write_partition` before this -- `BacktestOrchestrator` only reads from
`historical_data_root` via DuckDB, so every `POST /api/backtests` against a real deployment found
an empty dataset and raised `InsufficientHistoricalData`. This is the missing writer.

Persistence of ingestion *progress* is the one exception to this codebase's "application services
are DB-free" convention (see `BacktestOrchestrator`'s own docstring): without a durable cursor per
(instrument, timeframe), a periodic re-run would re-fetch an overlapping window and publish a
second overlapping Parquet partition for it -- `HistoricalStore.write_partition` has no natural
dedup key, so `read_candles` would then return duplicate rows for that window. `CursorStore` is
the narrow port that avoids this; `HistoricalIngestionCursorRepository` is its Postgres
implementation, symmetric with `KrakenTransport` being defined next to the one adapter that needs
it.

Quality gating follows DATA.md: "Required-field gaps, staleness or failed synchronization are
blocking" -- a FAILURE-status fetch is never written. The cursor still advances past it, though:
this repo has no quarantine mechanism yet (PENDING.md tracks that separately), and never advancing
would mean one permanently bad candle wedges ingestion for that instrument forever. Each
instrument is ingested independently and never lets another instrument's failure stop the batch.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from wallybot.data.historical import HistoricalStore
from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.clock import Clock
from wallybot.domain.market import TIMEFRAME_DURATIONS, Candle, Instrument, MarketDataProvider
from wallybot.domain.quality import QualityStatus

DEFAULT_BOOTSTRAP_LOOKBACK_CANDLES = 720
DEFAULT_FETCH_LIMIT = 720
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_FETCH_TIMEOUT_SECONDS = 15.0


class CursorStore(Protocol):
    async def get(self, instrument_id: str, timeframe: str) -> datetime | None: ...

    async def set(self, instrument_id: str, timeframe: str, last_close_time: datetime) -> None: ...


@dataclass(frozen=True)
class InstrumentIngestionOutcome:
    instrument_id: str
    fetched_candles: int
    written_part_ids: tuple[str, ...]
    quality_status: str | None
    cursor: datetime | None
    error: str | None


@dataclass(frozen=True)
class IngestionSummary:
    as_of: datetime
    outcomes: tuple[InstrumentIngestionOutcome, ...]


def _group_by_date(candles: list[Candle]) -> dict[str, list[Candle]]:
    groups: dict[str, list[Candle]] = {}
    for candle in candles:
        groups.setdefault(candle.open_time.date().isoformat(), []).append(candle)
    return groups


async def _ingest_instrument(
    instrument: Instrument,
    provider: MarketDataProvider,
    store: HistoricalStore,
    clock: Clock,
    timeframe: str,
    bootstrap_lookback_candles: int,
    quality_policy: QualityPolicy,
    cursor_store: CursorStore,
    fetch_limit: int,
    fetch_timeout_seconds: float,
) -> InstrumentIngestionOutcome:
    now = clock.now()
    cursor = await cursor_store.get(instrument.id, timeframe)
    since = cursor if cursor is not None else now - TIMEFRAME_DURATIONS[timeframe] * (
        bootstrap_lookback_candles
    )

    try:
        async with asyncio.timeout(fetch_timeout_seconds):
            candles = await provider.fetch_candles(instrument, timeframe, since, fetch_limit)
    except Exception as exc:
        return InstrumentIngestionOutcome(
            instrument_id=instrument.id,
            fetched_candles=0,
            written_part_ids=(),
            quality_status=None,
            cursor=cursor,
            error=f"{type(exc).__name__}: {exc}",
        )

    # Defensive against an inclusive `since` boundary or a retried overlapping fetch: never
    # reconsider a candle already advanced past.
    if cursor is not None:
        candles = [c for c in candles if c.close_time > cursor]
    if not candles:
        return InstrumentIngestionOutcome(instrument.id, 0, (), None, cursor, None)

    report = evaluate_series_quality(candles, quality_policy, now)
    latest_close = max(c.close_time for c in candles)

    if report.status is QualityStatus.FAILURE:
        await cursor_store.set(instrument.id, timeframe, latest_close)
        return InstrumentIngestionOutcome(
            instrument.id, len(candles), (), report.status.value, latest_close, None
        )

    written: list[str] = []
    for _date, group in sorted(_group_by_date(candles).items()):
        manifest = await asyncio.to_thread(store.write_partition, group, report.status.value)
        written.append(manifest.part_id)
        # Advance immediately after each partition so a crash mid-batch never leaves a published
        # partition behind an unmoved cursor -- the next run would otherwise refetch and
        # duplicate it.
        await cursor_store.set(instrument.id, timeframe, max(c.close_time for c in group))

    return InstrumentIngestionOutcome(
        instrument.id, len(candles), tuple(written), report.status.value, latest_close, None
    )


async def ingest_market_data(
    provider: MarketDataProvider,
    store: HistoricalStore,
    clock: Clock,
    timeframe: str,
    quality_policy: QualityPolicy,
    cursor_store: CursorStore,
    bootstrap_lookback_candles: int = DEFAULT_BOOTSTRAP_LOOKBACK_CANDLES,
    fetch_limit: int = DEFAULT_FETCH_LIMIT,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    fetch_timeout_seconds: float = DEFAULT_FETCH_TIMEOUT_SECONDS,
) -> IngestionSummary:
    instruments = await provider.discover_instruments()
    semaphore = asyncio.Semaphore(max_concurrency)

    async def bounded(instrument: Instrument) -> InstrumentIngestionOutcome:
        async with semaphore:
            return await _ingest_instrument(
                instrument,
                provider,
                store,
                clock,
                timeframe,
                bootstrap_lookback_candles,
                quality_policy,
                cursor_store,
                fetch_limit,
                fetch_timeout_seconds,
            )

    outcomes = await asyncio.gather(*(bounded(instrument) for instrument in instruments))
    return IngestionSummary(as_of=clock.now(), outcomes=tuple(outcomes))
