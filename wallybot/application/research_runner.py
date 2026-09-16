"""Executes one isolated research job per call by re-running the backtest an existing
`ExperimentRecord` already describes -- entirely from data already on disk (Parquet + Postgres),
never a live exchange adapter. `apps/research_worker` has no internet egress (PENDING.md's Fase 7
network isolation), so this is the only kind of research job it can run until that changes.

A claimed job that cannot be completed is always explicitly failed with a reason, never left
RUNNING forever and never silently dropped -- `ResearchJobRepository.claim_next` already marks it
RUNNING before this module sees it, so every code path here must reach `complete` or `fail`.
"""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.backtest_orchestrator import BacktestOrchestrator, BacktestRequest
from wallybot.data.historical_query import DEFAULT_QUERY_LIMITS
from wallybot.domain.experiment import ExperimentRecord
from wallybot.domain.market import Instrument, MarketType
from wallybot.infrastructure.experiment_repository import ExperimentRepository
from wallybot.infrastructure.research_job_repository import ResearchJobRepository
from wallybot.infrastructure.system_clock import SystemClock
from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator


class ExperimentNotFound(ValueError):
    """Raised when a research job's ``experiment_id`` has no matching row in
    ``experiment_records``.

    :param args: Passed through to :class:`ValueError`; the message identifies the missing
        ``experiment_id``.
    """


def _request_from_record(record: ExperimentRecord) -> BacktestRequest:
    """Rebuild the :class:`BacktestRequest` a prior backtest run used, from its persisted
    :class:`ExperimentRecord`.

    :param record: The original experiment to reproduce.
    :returns: A request equivalent to the one that produced ``record``, ready to hand to
        :class:`BacktestOrchestrator`.
    """
    return BacktestRequest(
        instrument_base=record.instrument_base,
        instrument_quote=record.instrument_quote,
        timeframe=record.timeframe,
        window_start=record.window_start,
        window_end=record.window_end,
        feature_window=record.feature_window,
        risk_off_threshold=record.risk_off_threshold,
        starting_equity=record.starting_equity,
        allocation_pct=record.allocation_pct,
        fee_rate=record.fee_rate,
        slippage_pct=record.slippage_pct,
        bootstrap_seed=record.seed,
    )


def _instrument_from_record(record: ExperimentRecord) -> Instrument:
    """Reconstruct the exact :class:`Instrument` (identity and precision) a prior backtest run
    used, from its persisted :class:`ExperimentRecord` -- never a fresh live lookup, since the
    research worker has no internet egress.

    :param record: The original experiment to reproduce.
    :returns: An :class:`Instrument` equal in every field to the one the original run resolved.
    """
    return Instrument(
        venue=record.instrument_venue,
        market_type=MarketType(record.instrument_market_type),
        base=record.instrument_base,
        quote=record.instrument_quote,
        price_increment=record.price_increment,
        quantity_increment=record.quantity_increment,
        min_quantity=record.min_quantity,
    )


async def run_pending_research_job(
    sessions: async_sessionmaker[AsyncSession], data_root: Path, now: int
) -> None:
    """Claim and execute at most one pending ``RESEARCH`` job.

    Looks up the job's ``experiment_id``, re-runs that backtest entirely from local Parquet data
    (no live exchange call, no network), persists the new result as a fresh
    :class:`ExperimentRecord`, and marks the job ``COMPLETED`` with the new record's id as its
    artifact. Any failure along the way -- missing experiment, insufficient historical data, an
    unexpected error -- marks the job ``FAILED`` with the exception message as the reason instead
    of raising, so a bad job never crashes the calling process's tick loop.

    :param sessions: Session factory scoped to the caller's database role (``wally_research`` in
        production).
    :param data_root: Root directory of the checksummed Parquet dataset (``HISTORICAL_DATA_ROOT``).
    :param now: Current Unix timestamp, used for the job's ``claimed_at``/``completed_at``.
    :returns: ``None`` in every case; outcomes are observable only via the job row itself.
    """
    research_jobs = ResearchJobRepository(sessions)
    job = await research_jobs.claim_next(now)
    if job is None:
        return

    experiment_id = job.payload["experiment_id"]
    try:
        async with sessions() as db:
            original = await ExperimentRepository(db).get(experiment_id)
        if original is None:
            raise ExperimentNotFound(f"experiment_records has no row for {experiment_id!r}")

        orchestrator = BacktestOrchestrator(
            provider=None,
            data_root=data_root,
            resource_limits=DEFAULT_QUERY_LIMITS,
            clock=SystemClock(),
            id_generator=UuidIdGenerator(),
        )
        outcome = await orchestrator.run(
            _request_from_record(original), _instrument_from_record(original)
        )

        async with sessions.begin() as db:
            await ExperimentRepository(db).save(outcome.record)
    except Exception as exc:
        await research_jobs.fail(job.id, now, str(exc))
        return

    await research_jobs.complete(job.id, now, outcome.record.experiment_id)
