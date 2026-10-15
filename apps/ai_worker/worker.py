"""Native host worker that creates operator-scoped AI proposals.

Runs natively on the host (not a container) because it needs normal access to the user's own
already-authenticated `claude`/`codex` CLI. Connects to Postgres over the loopback-only port
`docker-compose.yml` publishes for exactly this process. No Redis dependency: a single
independent polling loop has nothing to subscribe a scheduler wakeup from.
"""

import asyncio
import logging
import signal
import tempfile
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from wallybot.application.ai_decision_loop import run_ai_decision_tick
from wallybot.data.quality import QualityPolicy
from wallybot.domain.market import MarketDataProvider
from wallybot.exchanges.binance import CURATED_USDT_PAIRS, BinanceExchange
from wallybot.exchanges.kraken import KrakenExchange
from wallybot.infrastructure.ai_worker_settings import AiWorkerSettings, load_ai_worker_settings
from wallybot.infrastructure.live_models import AnalystPortfolioRow
from wallybot.infrastructure.logging import configure_logging
from wallybot.infrastructure.models import AiAutonomyControlRow, ControlRow, UserRow
from wallybot.infrastructure.system_clock import SystemClock
from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator
from wallybot.intelligence.cli_ai_provider import CliAiProvider
from wallybot.intelligence.consensus_ai_provider import ConsensusAiProvider
from wallybot.market.universe import UniverseFilterConfig

# A tick that consults no analyst re-checks availability at most this often (one HOLD call).
_STATUS_REFRESH_SECONDS = 3600


def _write_heartbeat(now: int) -> None:
    folder = Path(tempfile.gettempdir())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "wally-ai_worker.heartbeat").write_text(str(now))


async def _heartbeat_loop(sessions, stopping: asyncio.Event, logger) -> None:
    while not stopping.is_set():
        try:
            now = int(time.time())
            async with sessions.begin() as db:
                await db.execute(
                    text("SELECT public.record_ai_worker_heartbeat(:now)"), {"now": now}
                )
            await asyncio.to_thread(_write_heartbeat, now)
        except Exception:
            logger.warning("AI_WORKER_HEARTBEAT_FAILED")
        try:
            await asyncio.wait_for(stopping.wait(), timeout=10)
        except TimeoutError:
            pass


async def run_ai_worker() -> None:
    settings = load_ai_worker_settings()
    logger = configure_logging("ai_worker")
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        connect_args={"connect_timeout": 5},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    clock = SystemClock()
    id_generator = UuidIdGenerator()
    # The analyst studies the real account's own exchange; Binance is the default otherwise.
    provider: dict[str, MarketDataProvider] = {
        "kraken": KrakenExchange(clock=clock),
        "binance": BinanceExchange(clock=clock, symbols=CURATED_USDT_PAIRS),
    }
    quality_policy = QualityPolicy(
        version=1,
        timeframe="1h",
        max_stale_age=timedelta(hours=3),
        max_clock_drift=timedelta(minutes=5),
        max_abnormal_return=Decimal("0.5"),
    )
    universe_config = UniverseFilterConfig(
        version=1,
        min_history_candles=20,
        min_average_quote_volume=Decimal("0"),
        max_spread_ratio=Decimal("0.05"),
    )

    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            pass  # Windows: the launcher terminates this tracked child process directly.

    heartbeat = asyncio.create_task(_heartbeat_loop(sessions, stopping, logger))
    status_recorded_at: dict[str, int] = {}
    last_analysis: dict[str, float] = {}
    try:
        # Immediate check on startup so the UI shows fresh state as soon as the worker is running.
        await _check_analyst_availability(sessions, provider, settings, id_generator, clock, logger, status_recorded_at)
        while not stopping.is_set():
            try:
                await _tick(
                    sessions,
                    provider,
                    settings,
                    id_generator,
                    quality_policy,
                    universe_config,
                    clock,
                    logger,
                    status_recorded_at,
                    last_analysis,
                )
            except Exception:
                logger.warning("AI_WORKER_TICK_FAILED")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=settings.ai_poll_interval_seconds)
            except TimeoutError:
                pass
    finally:
        stopping.set()
        await heartbeat
        await engine.dispose()


async def _check_analyst_availability(
    sessions: async_sessionmaker[AsyncSession],
    provider: dict[str, MarketDataProvider],
    settings: AiWorkerSettings,
    id_generator: UuidIdGenerator,
    clock: SystemClock,
    logger: logging.LoggerAdapter,
    status_recorded_at: dict[str, int],
) -> None:
    """Run check_ready() for each configured analyst regardless of the normal refresh interval."""
    async with sessions() as db:
        control = await db.get(AiAutonomyControlRow, 1)
    if control is None:
        return
    analysts = []
    if control.codex_enabled:
        analysts.append(CliAiProvider(cli="codex", model_id=settings.codex_model_id, prompt_version=settings.ai_prompt_version, id_generator=id_generator, clock=clock, timeout_seconds=settings.ai_timeout_seconds))
    if control.claude_enabled:
        analysts.append(CliAiProvider(cli="claude", model_id=settings.claude_model_id, prompt_version=settings.ai_prompt_version, id_generator=id_generator, clock=clock, timeout_seconds=settings.ai_timeout_seconds))
    for analyst in analysts:
        analyst._last_call_ok = None  # force check_ready() path in _report_analyst_status
    status_recorded_at.clear()
    await _report_analyst_status(sessions, analysts, status_recorded_at, logger)


async def _tick(
    sessions: async_sessionmaker[AsyncSession],
    provider: dict[str, MarketDataProvider],
    settings: AiWorkerSettings,
    id_generator: UuidIdGenerator,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    clock: SystemClock,
    logger: logging.LoggerAdapter,
    status_recorded_at: dict[str, int],
    last_analysis: dict[str, float],
) -> None:
    # An operator check ("Iniciar"/"Comprobar ahora") runs right away, before any gate that
    # could skip this tick (stale portfolio context, analysis interval, AI paused).
    async with sessions.begin() as db:
        row = await db.get(AiAutonomyControlRow, 1, with_for_update=True)
        check_requested = row is not None and row.check_requested
        if check_requested:
            row.check_requested = False
    if check_requested:
        await _check_analyst_availability(
            sessions, provider, settings, id_generator, clock, logger, status_recorded_at
        )

    async with sessions() as db:
        control = await db.get(AiAutonomyControlRow, 1)
        instance = await db.get(ControlRow, 1)
        portfolio = None
        admin_id = await db.scalar(
            select(UserRow.id).where(UserRow.role == "ADMIN").order_by(UserRow.created_at)
        )
        if instance is not None and instance.environment == "LIVE":
            portfolio = await db.scalar(
                select(AnalystPortfolioRow).order_by(AnalystPortfolioRow.as_of.desc()).limit(1)
            )
            if portfolio is None or not timedelta(0) <= clock.now() - portfolio.as_of <= timedelta(
                seconds=60
            ):
                logger.warning("AI_PORTFOLIO_CONTEXT_UNAVAILABLE")
                return
            admin_id = await db.scalar(
                select(UserRow.id).where(UserRow.id == portfolio.owner_id, UserRow.role == "ADMIN")
            )
    if control is None or control.status != "ENABLED" or admin_id is None:
        return

    analysts = []
    if control.codex_enabled:
        analysts.append(
            CliAiProvider(
                cli="codex",
                model_id=settings.codex_model_id,
                prompt_version=settings.ai_prompt_version,
                id_generator=id_generator,
                clock=clock,
                timeout_seconds=settings.ai_timeout_seconds,
            )
        )
    if control.claude_enabled:
        analysts.append(
            CliAiProvider(
                cli="claude",
                model_id=settings.claude_model_id,
                prompt_version=settings.ai_prompt_version,
                id_generator=id_generator,
                clock=clock,
                timeout_seconds=settings.ai_timeout_seconds,
            )
        )
    if not analysts:
        logger.warning("AI_WORKER_NO_ANALYST_CONFIGURED")
        return

    holdings = (
        tuple((asset, Decimal(quantity)) for asset, quantity in portfolio.holdings.items())
        if portfolio
        else ()
    )
    starter = bool(control.starter_requested)
    if starter:
        async with sessions.begin() as db:
            row = await db.get(AiAutonomyControlRow, 1, with_for_update=True)
            if row is not None:
                row.starter_requested = False
        if holdings:
            logger.info("AI_STARTER_SKIPPED_HOLDINGS_PRESENT")
            starter = False
    # Flat accounts are scanned often; once something was bought, re-evaluate every few hours.
    interval = (
        settings.ai_holding_analysis_interval_seconds
        if holdings
        else settings.ai_flat_analysis_interval_seconds
    )
    if not starter and time.monotonic() - last_analysis.get("at", float("-inf")) < interval:
        # Idle ticks still refresh availability (rate-limited) so the UI never goes stale.
        await _report_analyst_status(sessions, analysts, status_recorded_at, logger)
        return
    last_analysis["at"] = time.monotonic()

    try:
        await _analyze(
            sessions,
            provider[portfolio.venue if portfolio is not None else "binance"],
            analysts,
            control,
            admin_id,
            portfolio,
            quality_policy,
            universe_config,
            clock,
            logger,
            holdings,
            starter,
        )
    finally:
        await _report_analyst_status(sessions, analysts, status_recorded_at, logger)


async def _report_analyst_status(
    sessions: async_sessionmaker[AsyncSession],
    analysts: list[CliAiProvider],
    recorded_at: dict[str, int],
    logger: logging.LoggerAdapter,
) -> None:
    """Expose per-CLI availability to the operator; never changes analyst or consensus settings."""
    for analyst in analysts:
        now = int(time.time())
        available = analyst.last_call_ok
        if available is None:
            if now - recorded_at.get(analyst.cli, 0) < _STATUS_REFRESH_SECONDS:
                continue
            available = await analyst.check_ready()
        if not available:
            logger.warning(f"AI_ANALYST_UNAVAILABLE_{analyst.cli.upper()}")
        try:
            async with sessions.begin() as db:
                await db.execute(
                    text("SELECT public.record_ai_analyst_status(:analyst, :available, :now)"),
                    {"analyst": analyst.cli, "available": available, "now": now},
                )
            recorded_at[analyst.cli] = now
        except Exception:
            logger.warning("AI_ANALYST_STATUS_FAILED")


async def _analyze(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    analysts: list[CliAiProvider],
    control: AiAutonomyControlRow,
    admin_id: str,
    portfolio: AnalystPortfolioRow | None,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    clock: SystemClock,
    logger: logging.LoggerAdapter,
    holdings: tuple[tuple[str, Decimal], ...],
    starter: bool,
) -> None:
    result = await run_ai_decision_tick(
        sessions=sessions,
        provider=provider,
        ai_provider=ConsensusAiProvider(
            providers=tuple(analysts), require_consensus=control.require_consensus
        ),
        quality_policy=quality_policy,
        universe_config=universe_config,
        owner_id=admin_id,
        now=clock.now(),
        allocation_guidance=(
            ("CORE", control.target_core_pct),
            ("GROWTH", control.target_growth_pct),
            ("SPECULATIVE", control.target_speculative_pct),
        ),
        portfolio_cash_usd=portfolio.cash_usd if portfolio else None,
        portfolio_holdings=holdings,
        portfolio_as_of=portfolio.as_of if portfolio else None,
        starter_position=starter,
    )
    logger.info(
        "AI_WORKER_TICK_COMPLETED",
        extra={
            "instruments_evaluated": result.instruments_evaluated,
            "proposals_received": result.proposals_received,
            "proposals_persisted": result.proposals_persisted,
            "starter": starter,
        },
    )
