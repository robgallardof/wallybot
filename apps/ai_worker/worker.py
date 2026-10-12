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
    provider = KrakenExchange(clock=clock)
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
    try:
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


async def _tick(
    sessions: async_sessionmaker[AsyncSession],
    provider: KrakenExchange,
    settings: AiWorkerSettings,
    id_generator: UuidIdGenerator,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    clock: SystemClock,
    logger: logging.LoggerAdapter,
) -> None:
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
        portfolio_holdings=tuple(
            (asset, Decimal(quantity)) for asset, quantity in portfolio.holdings.items()
        )
        if portfolio
        else (),
        portfolio_as_of=portfolio.as_of if portfolio else None,
    )
    logger.info(
        "AI_WORKER_TICK_COMPLETED",
        extra={
            "instruments_evaluated": result.instruments_evaluated,
            "proposals_received": result.proposals_received,
            "proposals_persisted": result.proposals_persisted,
        },
    )
