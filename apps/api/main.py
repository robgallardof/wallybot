import asyncio
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from functools import partial
from uuid import uuid4

import httpx
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.auth_routes import router as auth_router
from apps.api.backtest_routes import router as backtest_router
from apps.api.connection_routes import router as connection_router
from apps.api.intelligence_routes import router as intelligence_router
from apps.api.market_routes import router as market_router
from apps.api.portfolio_routes import paper_account_id
from apps.api.portfolio_routes import router as portfolio_router
from apps.api.research_routes import router as research_router
from apps.api.risk_routes import router as risk_router
from apps.api.system_routes import router as system_router
from apps.api.telegram_routes import router as telegram_router
from wallybot.application.backtest_orchestrator import BacktestOrchestrator
from wallybot.application.decision_loop import run_decision_tick
from wallybot.application.execution_service import ExecutionService
from wallybot.application.market_ingestion import ingest_market_data
from wallybot.application.market_overview import build_market_overview
from wallybot.application.price_consensus_job import ProviderSource, run_price_consensus_tick
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.application.telegram_command_loop import run_telegram_command_tick
from wallybot.application.telegram_report_job import run_telegram_report_tick
from wallybot.data.historical import HistoricalStore
from wallybot.data.historical_query import DEFAULT_QUERY_LIMITS
from wallybot.data.quality import QualityPolicy
from wallybot.domain.breaker import BreakerType
from wallybot.domain.control import Environment, Status
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.domain.provider_reliability import ProviderCallOutcome
from wallybot.exchanges.fake import FakeExchange
from wallybot.exchanges.kraken import KrakenExchange
from wallybot.infrastructure.database import database
from wallybot.infrastructure.historical_ingestion_cursor_repository import (
    HistoricalIngestionCursorRepository,
)
from wallybot.infrastructure.logging import configure_logging
from wallybot.infrastructure.metrics import (
    ACTIVE_BREAKERS,
    DECISION_TICK_DURATION,
    DECISION_TICKS,
    MARKET_INGESTION_TICKS,
    ORDERS_PLACED,
    PRICE_CONSENSUS_TICKS,
    RECONCILIATION_HEALTHY,
    RECONCILIATION_UNKNOWN_ORDERS,
    SERVICE_HEARTBEAT_AGE,
    TELEGRAM_COMMAND_TICKS,
)
from wallybot.infrastructure.models import ControlRow, HeartbeatRow, UserRow
from wallybot.infrastructure.settings import Settings, load_settings
from wallybot.infrastructure.system_clock import SystemClock
from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator
from wallybot.market.universe import UniverseFilterConfig
from wallybot.notifications.telegram import HttpxTelegramTransport
from wallybot.security.auth import AuthError, AuthService
from wallybot.security.crypto import Crypto
from wallybot.security.throttle import Throttle, Throttled

REQUESTS = Counter("wallybot_http_requests_total", "Requests by status class", ["status_class"])

# `worker`/`scheduler` sit on the `operational` Docker network, which is internal-only (no
# internet egress) by design -- `api` is the only backend process on `edge`, so the ingestion job
# that persists Kraken candles to Parquet has to live here, next to the KrakenExchange instance
# `build_market_overview` already uses. Same timeframe/thresholds as that overview, since this job
# persists what that endpoint only ever showed ephemerally.
MARKET_INGESTION_TIMEFRAME = "1h"
MARKET_INGESTION_INTERVAL_SECONDS = 3600


# Independent of `apps/api/system_routes.py`'s `/api/system` route (which also refreshes this
# same gauge, but only when someone actually loads the System page) -- a metric that only updates
# on UI traffic defeats the point of background alerting, so this loop keeps it fresh on its own,
# same as every other metric in this file.
HEARTBEAT_METRICS_INTERVAL_SECONDS = 30


async def _heartbeat_metrics_loop(sessions, logger) -> None:
    while True:
        try:
            now = int(time.time())
            async with sessions() as db:
                beats = (await db.scalars(select(HeartbeatRow))).all()
            for beat in beats:
                SERVICE_HEARTBEAT_AGE.labels(beat.service).set(max(0, now - beat.timestamp))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("HEARTBEAT_METRICS_TICK_FAILED")
        await asyncio.sleep(HEARTBEAT_METRICS_INTERVAL_SECONDS)


async def _market_ingestion_loop(
    provider: KrakenExchange,
    store: HistoricalStore,
    clock: SystemClock,
    quality_policy: QualityPolicy,
    cursor_store: HistoricalIngestionCursorRepository,
    logger,
) -> None:
    while True:
        try:
            summary = await ingest_market_data(
                provider=provider,
                store=store,
                clock=clock,
                timeframe=MARKET_INGESTION_TIMEFRAME,
                quality_policy=quality_policy,
                cursor_store=cursor_store,
            )
            written = sum(len(o.written_part_ids) for o in summary.outcomes)
            errors = sum(1 for o in summary.outcomes if o.error)
            logger.info(
                "MARKET_DATA_INGESTED",
                extra={
                    "instruments": len(summary.outcomes),
                    "partitions_written": written,
                    "errors": errors,
                },
            )
            MARKET_INGESTION_TICKS.labels("success").inc()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("MARKET_DATA_INGESTION_FAILED")
            MARKET_INGESTION_TICKS.labels("failure").inc()
        await asyncio.sleep(MARKET_INGESTION_INTERVAL_SECONDS)


# Matches `wallybot.domain.price_consensus.DEFAULT_MAX_STALENESS` (5 minutes) so a quote is never
# considered stale purely because this loop's own cadence is too slow.
PRICE_CONSENSUS_INTERVAL_SECONDS = 300

# The Markets page's own KrakenExchange: broader than `provider`'s default (XBTUSD/ETHUSD only,
# used for ingestion/backtests/price-consensus, deliberately narrow so Parquet storage and API
# usage stay bounded). Kraken's public AssetPairs endpoint lists ~1450 pairs when queried with no
# filter -- verified against the real API -- far too many to fetch candles/snapshots for on every
# page load even with bounded concurrency. This is a curated set of major, liquid USD pairs
# (symbols verified against Kraken's real `altname` field, not guessed -- Kraken uses its own
# codes for some assets, e.g. Bitcoin is "XBT" and Dogecoin is "XDG", not "BTC"/"DOGE").
MARKET_OVERVIEW_PAIRS = (
    "XBTUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "XDGUSD", "LTCUSD", "DOTUSD",
    "LINKUSD", "POLUSD", "AVAXUSD", "BCHUSD", "XLMUSD", "UNIUSD", "ATOMUSD", "ETCUSD",
    "FILUSD", "NEARUSD", "APTUSD", "ARBUSD", "TRXUSD", "SHIBUSD", "SUIUSD", "OPUSD",
)


async def _price_consensus_loop(
    sessions,
    crypto: Crypto,
    static_sources: list[ProviderSource],
    clock: SystemClock,
    logger,
) -> None:
    outcomes: dict[str, deque[ProviderCallOutcome]] = {}
    while True:
        try:
            await run_price_consensus_tick(
                sessions, crypto, clock, static_sources, clock.now(), outcomes
            )
            logger.info("PRICE_CONSENSUS_COMPUTED")
            PRICE_CONSENSUS_TICKS.labels("success").inc()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("PRICE_CONSENSUS_TICK_FAILED")
            PRICE_CONSENSUS_TICKS.labels("failure").inc()
        await asyncio.sleep(PRICE_CONSENSUS_INTERVAL_SECONDS)


# The first closed loop from market data to a submitted PAPER order (`DecisionPipeline`,
# Phase 3 Slice 9) had no live caller anywhere -- every downstream piece (allocator, risk engine,
# execution service, ledger) was real and tested, but nothing ever actually ran the loop in
# production. Lives in `apps/api` for the same reason as `_market_ingestion_loop`/
# `_price_consensus_loop`: only this process has internet egress to reach Kraken. The tick itself
# (`run_decision_tick`) lives in `wallybot.application.decision_loop`, same split as
# `ingest_market_data`/`run_price_consensus_tick`; this wrapper only resolves "which account" from
# real control/user state each tick. `paper_gateway`/`execution`/`reconciliation` are constructed
# once in `create_app`'s lifespan (not lazily in here) and also stored on `app.state` -- the
# cancel-order route needs the *same* `ExecutionService`/`FakeExchange` instance this loop submits
# orders through, since FakeExchange's own in-memory order state lives on that one instance.
#
# Single admin, single account: there is no multi-user account administration yet (PENDING.md
# Fase 1) to pick a different one.
DECISION_INTERVAL_SECONDS = 300


async def _decision_loop(
    sessions,
    provider: KrakenExchange,
    paper_gateway: FakeExchange,
    execution: ExecutionService,
    reconciliation: ReconciliationService,
    clock: SystemClock,
    id_generator: UuidIdGenerator,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    logger,
) -> None:
    while True:
        try:
            async with sessions() as db:
                control = await db.get(ControlRow, 1)
                admin_id = await db.scalar(
                    select(UserRow.id).where(UserRow.role == "ADMIN").order_by(UserRow.created_at)
                )
            if (
                control is None
                or not control.setup_complete
                or control.status != Status.RUNNING
                or control.environment != Environment.PAPER
                or admin_id is None
            ):
                await asyncio.sleep(DECISION_INTERVAL_SECONDS)
                continue

            tick_started = time.monotonic()
            result = await run_decision_tick(
                sessions=sessions,
                provider=provider,
                paper_gateway=paper_gateway,
                execution=execution,
                reconciliation=reconciliation,
                clock=clock,
                id_generator=id_generator,
                quality_policy=quality_policy,
                universe_config=universe_config,
                account_id=paper_account_id(admin_id),
                now=clock.now(),
            )
            DECISION_TICK_DURATION.observe(time.monotonic() - tick_started)
            orders_placed = sum(
                1 for outcome in result.outcomes if outcome.order_status is not None
            )
            logger.info(
                "DECISION_TICK_COMPLETED",
                extra={
                    "instruments_evaluated": len(result.outcomes),
                    "orders_placed": orders_placed,
                    "reconciliation_healthy": result.reconciliation_healthy,
                    "active_breakers": [b.breaker_type.value for b in result.active_breakers],
                },
            )
            DECISION_TICKS.labels("success").inc()
            ORDERS_PLACED.inc(orders_placed)
            RECONCILIATION_HEALTHY.set(1 if result.reconciliation_healthy else 0)
            RECONCILIATION_UNKNOWN_ORDERS.set(result.reconciliation_unknown_orders)
            active_types = {b.breaker_type.value for b in result.active_breakers}
            for breaker_type in BreakerType:
                ACTIVE_BREAKERS.labels(breaker_type.value).set(
                    1 if breaker_type.value in active_types else 0
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("DECISION_TICK_FAILED")
            DECISION_TICKS.labels("failure").inc()
        await asyncio.sleep(DECISION_INTERVAL_SECONDS)


# The tick itself (`run_telegram_command_tick`) lives in
# `wallybot.application.telegram_command_loop`, same split as `ingest_market_data`/
# `run_price_consensus_tick`/`run_decision_tick` -- this wrapper
# only resolves "which account" from real admin/user state each tick, the one lookup that stays out
# of the application layer. Telegram's own `getUpdates` long-poll (8s, see that module's docstring)
# already paces this loop; no extra sleep on the success path, only on a failed tick.
async def _telegram_command_loop(
    sessions,
    crypto: Crypto,
    transport,
    clock: SystemClock,
    id_generator: UuidIdGenerator,
    logger,
) -> None:
    while True:
        try:
            async with sessions() as db:
                admin_id = await db.scalar(
                    select(UserRow.id).where(UserRow.role == "ADMIN").order_by(UserRow.created_at)
                )
            account_id = paper_account_id(admin_id) if admin_id is not None else None
            await run_telegram_command_tick(
                sessions, crypto, transport, id_generator, account_id, clock.now()
            )
            TELEGRAM_COMMAND_TICKS.labels("success").inc()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("TELEGRAM_COMMAND_TICK_FAILED")
            TELEGRAM_COMMAND_TICKS.labels("failure").inc()
            await asyncio.sleep(5)


# Only cares about "has the UTC date/ISO week changed since the last report" (see
# `wallybot.application.telegram_report_job`'s own `last_sent_key` check), so this can poll far
# less often than the 8s Telegram long-poll above -- 30 minutes is prompt enough after a
# day/week boundary without adding meaningful load. The tick itself
# (`run_telegram_report_tick`) lives in `wallybot.application.telegram_report_job`, same split
# as every other loop in this module.
TELEGRAM_REPORT_INTERVAL_SECONDS = 1800


async def _telegram_report_loop(
    sessions,
    crypto: Crypto,
    transport,
    throttle: NotificationThrottle,
    clock: SystemClock,
    logger,
) -> None:
    while True:
        try:
            async with sessions() as db:
                admin_id = await db.scalar(
                    select(UserRow.id).where(UserRow.role == "ADMIN").order_by(UserRow.created_at)
                )
            if admin_id is not None:
                await run_telegram_report_tick(
                    sessions,
                    crypto,
                    transport,
                    throttle,
                    paper_account_id(admin_id),
                    "PAPER",
                    clock.now(),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("TELEGRAM_REPORT_TICK_FAILED")
        await asyncio.sleep(TELEGRAM_REPORT_INTERVAL_SECONDS)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()
    logger = configure_logging("api")
    # Resolved once from migrations/versions at process start rather than hardcoded -- previously
    # this had to be bumped by hand on every migration (0016 through 0022, five times).
    expected_revision = ScriptDirectory.from_config(AlembicConfig("alembic.ini")).get_current_head()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine, sessions = database(config)
        redis = Redis.from_url(
            config.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
        )
        app.state.settings, app.state.sessions = config, sessions
        app.state.redis = redis
        app.state.auth = AuthService(sessions, config)
        app.state.throttle = Throttle(redis, config.auth_limit, config.auth_window_seconds)
        telegram_client = httpx.AsyncClient(timeout=10.0)
        app.state.telegram_transport = HttpxTelegramTransport(telegram_client)
        app.state.notification_throttle = NotificationThrottle()

        clock = SystemClock()
        provider = KrakenExchange(clock=clock)
        quality_policy = QualityPolicy(
            version=1,
            timeframe=MARKET_INGESTION_TIMEFRAME,
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        )
        # Shared with `_decision_loop` below -- same liquidity/history/spread eligibility bar for
        # whatever the pipeline may actually trade as what the Markets page already shows browsing.
        decision_universe_config = UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        )
        app.state.market_overview = partial(
            build_market_overview,
            provider=KrakenExchange(clock=clock, pairs=MARKET_OVERVIEW_PAIRS),
            clock=clock,
            timeframe="1h",
            history_candles=30,
            universe_config=decision_universe_config,
            quality_policy=quality_policy,
            feature_window=20,
        )
        app.state.backtest_orchestrator = BacktestOrchestrator(
            provider=provider,
            data_root=config.historical_data_root,
            resource_limits=DEFAULT_QUERY_LIMITS,
            clock=clock,
            id_generator=UuidIdGenerator(),
        )
        # Shared by `_decision_loop` and the order-cancellation route (`portfolio_routes.py`) --
        # both must submit/cancel through the *same* FakeExchange instance, since its in-memory
        # order state (`_orders`/`_fills`) lives on that one object, not the ledger.
        paper_gateway = FakeExchange(clock=clock, market_data=provider)
        execution = ExecutionService(gateway=paper_gateway, sessions=sessions, clock=clock)
        reconciliation = ReconciliationService(execution=execution, sessions=sessions)
        app.state.execution = execution
        heartbeat_metrics_task = asyncio.create_task(_heartbeat_metrics_loop(sessions, logger))
        ingestion_task = asyncio.create_task(
            _market_ingestion_loop(
                provider=provider,
                store=HistoricalStore(config.historical_data_root, clock, UuidIdGenerator()),
                clock=clock,
                quality_policy=quality_policy,
                cursor_store=HistoricalIngestionCursorRepository(sessions),
                logger=logger,
            )
        )
        # Skipped under the integration test suite: `client`-based tests share one Postgres
        # container for the whole run, and `list_latest()` on price_consensus_results/
        # provider_reliability_snapshots picks the single most recent row across ALL tests --
        # a real-clock background tick from this loop would non-deterministically "win" over
        # whatever a given test seeded, flaking tests it has nothing to do with. Tests that
        # exercise this job call `run_price_consensus_tick`/`_tiingo_source` directly instead.
        price_consensus_task = (
            None
            if config.environment == "test"
            else asyncio.create_task(
                _price_consensus_loop(
                    sessions,
                    app.state.auth.crypto,
                    [ProviderSource("kraken", provider)],
                    clock,
                    logger,
                )
            )
        )
        # Same reasoning and same test-suite exclusion as price_consensus_task immediately above:
        # a real-clock tick against the shared test Postgres container would flake unrelated tests,
        # and this job also submits real PAPER orders -- something no test in this suite expects
        # to happen on its own. Tests exercise DecisionPipeline directly instead.
        decision_task = (
            None
            if config.environment == "test"
            else asyncio.create_task(
                _decision_loop(
                    sessions,
                    provider,
                    paper_gateway,
                    execution,
                    reconciliation,
                    clock,
                    UuidIdGenerator(),
                    quality_policy,
                    decision_universe_config,
                    logger,
                )
            )
        )
        # Same test-suite exclusion as price_consensus_task/decision_task above: a real long-poll
        # against the live Telegram API has nothing to do with any test in this suite and would
        # just hang/error against a fake token.
        telegram_command_task = (
            None
            if config.environment == "test"
            else asyncio.create_task(
                _telegram_command_loop(
                    sessions,
                    app.state.auth.crypto,
                    app.state.telegram_transport,
                    clock,
                    UuidIdGenerator(),
                    logger,
                )
            )
        )
        # Same test-suite exclusion as price_consensus_task/decision_task/telegram_command_task
        # above: real-clock writes to `telegram_reports` against the shared test Postgres
        # container would non-deterministically race whatever a given test seeded/asserted, and
        # no test in this suite expects an outbound report on its own. Tests exercise
        # `run_telegram_report_tick` directly instead.
        telegram_report_task = (
            None
            if config.environment == "test"
            else asyncio.create_task(
                _telegram_report_loop(
                    sessions,
                    app.state.auth.crypto,
                    app.state.telegram_transport,
                    app.state.notification_throttle,
                    clock,
                    logger,
                )
            )
        )
        logger.info("API_STARTED")
        yield
        if telegram_report_task is not None:
            telegram_report_task.cancel()
            try:
                await telegram_report_task
            except asyncio.CancelledError:
                pass
        if telegram_command_task is not None:
            telegram_command_task.cancel()
            try:
                await telegram_command_task
            except asyncio.CancelledError:
                pass
        if decision_task is not None:
            decision_task.cancel()
            try:
                await decision_task
            except asyncio.CancelledError:
                pass
        if price_consensus_task is not None:
            price_consensus_task.cancel()
            try:
                await price_consensus_task
            except asyncio.CancelledError:
                pass
        ingestion_task.cancel()
        try:
            await ingestion_task
        except asyncio.CancelledError:
            pass
        heartbeat_metrics_task.cancel()
        try:
            await heartbeat_metrics_task
        except asyncio.CancelledError:
            pass
        await telegram_client.aclose()
        await redis.aclose()
        await engine.dispose()

    app = FastAPI(
        title="WallyBot", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        correlation = str(uuid4())
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin") != config.origin:
                return JSONResponse({"detail": "Origin rejected"}, status_code=403)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "JSON required"}, status_code=415)
            try:
                length = int(request.headers.get("content-length", "-1"))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            if length < 0:
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            if length > 16384:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
            body = await request.body()
            if len(body) > 16384:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        try:
            response = await call_next(request)
        except Exception:
            # Never allow default traceback logging to expose SQL parameters or credentials.
            logger.error("REQUEST_FAILED")
            response = JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Correlation-ID"] = correlation
        REQUESTS.labels(f"{response.status_code // 100}xx").inc()
        logger.info("HTTP_REQUEST_COMPLETED", extra={"correlation_id": correlation})
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request: Request, exc: AuthError):
        if request.url.path.startswith("/api/auth/") and request.method == "POST":
            await request.app.state.auth.failed("AUTHENTICATION_FAILED")
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic errors include rejected input by default; never echo passwords/tokens.
        return JSONResponse({"detail": "Invalid request fields"}, status_code=422)

    @app.exception_handler(Throttled)
    async def throttled(request: Request, exc: Throttled):
        return JSONResponse(
            {"detail": "Too many attempts; try later"},
            status_code=429,
            headers={"Retry-After": str(config.auth_window_seconds)},
        )

    async def unavailable(request: Request, exc: Exception):
        logger.warning("DEPENDENCY_UNAVAILABLE")
        return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)

    app.add_exception_handler(SQLAlchemyError, unavailable)
    app.add_exception_handler(RedisError, unavailable)

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    async def ready(request: Request):
        try:
            async with asyncio.timeout(5):
                async with request.app.state.sessions() as db:
                    revision = await db.scalar(text("SELECT version_num FROM alembic_version"))
                    if revision != expected_revision:
                        raise ValueError("Schema not ready")
                    if await db.scalar(text("SELECT id FROM control WHERE id = 1")) != 1:
                        raise ValueError("Control state not ready")
                await request.app.state.redis.ping()
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    # Unauthenticated: Prometheus can't hold a session cookie, so this relies on network
    # isolation instead, the same trust boundary this codebase already uses for
    # worker/scheduler/research (`internal: true` Docker networks, PENDING.md Fase 7). The
    # gateway's nginx config (`docker/gateway.conf`) has an explicit `location = /api/metrics
    # { return 404; }` block so this is never reachable from the public edge -- only Prometheus,
    # on the `operational` network alongside `api`, ever reaches it (`api:8000/api/metrics`
    # directly, bypassing the gateway).
    @app.get("/api/metrics")
    async def metrics():
        return Response(generate_latest(), media_type="text/plain; version=0.0.4")

    app.include_router(auth_router)
    app.include_router(connection_router)
    app.include_router(portfolio_router)
    app.include_router(system_router)
    app.include_router(market_router)
    app.include_router(research_router)
    app.include_router(intelligence_router)
    app.include_router(backtest_router)
    app.include_router(telegram_router)
    app.include_router(risk_router)
    return app
