import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import Counter, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from apps.api.auth_routes import router as auth_router
from apps.api.dependencies import SignedIn
from apps.api.system_routes import router as system_router
from wallybot.infrastructure.database import database
from wallybot.infrastructure.logging import configure_logging
from wallybot.infrastructure.settings import Settings, load_settings
from wallybot.security.auth import AuthError, AuthService
from wallybot.security.throttle import Throttle, Throttled

REQUESTS = Counter("wallybot_http_requests_total", "Requests by status class", ["status_class"])


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or load_settings()
    logger = configure_logging("api")

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
        logger.info("API_STARTED")
        yield
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
                    if revision != "0001_foundation":
                        raise ValueError("Schema not ready")
                    if await db.scalar(text("SELECT id FROM control WHERE id = 1")) != 1:
                        raise ValueError("Control state not ready")
                await request.app.state.redis.ping()
        except Exception:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    @app.get("/api/metrics")
    async def metrics(user: SignedIn):
        return Response(generate_latest(), media_type="text/plain; version=0.0.4")

    app.include_router(auth_router)
    app.include_router(system_router)
    return app
