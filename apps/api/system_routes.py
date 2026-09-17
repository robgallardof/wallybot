import time

from fastapi import APIRouter, Request
from sqlalchemy import select, text

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import ControlView, DashboardView, EventView, ServiceStatusView, SystemView
from apps.api.schemas import ControlChange
from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.control import Control, Environment, Role, Status
from wallybot.infrastructure.models import ControlRow, EventRow, HeartbeatRow
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.security.auth import AuthError, audit

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/dashboard", response_model=DashboardView)
async def dashboard(request: Request, user: SignedIn) -> DashboardView:
    async with request.app.state.sessions() as db:
        state = await db.get(ControlRow, 1)
        if state is None:
            raise AuthError("System not initialized", 503)
        return DashboardView(
            environment=state.environment,
            status=Status(state.status),
            trading_available=False,
            exchange="NOT_CONFIGURED",
            equity=None,
            positions=[],
            phase=1,
        )


@router.get("/system", response_model=SystemView)
async def system(request: Request, user: SignedIn) -> SystemView:
    async with request.app.state.sessions() as db:
        await db.execute(text("SELECT 1"))
        beats = (await db.scalars(select(HeartbeatRow))).all()
        telegram_config = await TelegramConfigRepository(db).get()
    telegram_ready = bool(
        telegram_config
        and telegram_config.enabled
        and telegram_config.encrypted_bot_token
        and telegram_config.chat_id is not None
    )
    redis_status = "HEALTHY"
    try:
        await request.app.state.redis.ping()
    except Exception:
        redis_status = "UNAVAILABLE"
    now = int(time.time())
    services = {
        beat.service: ServiceStatusView(
            age_seconds=max(0, now - beat.timestamp),
            status="HEALTHY" if 0 <= now - beat.timestamp < 30 else "STALE",
        )
        for beat in beats
    }
    for name in ("worker", "scheduler", "research"):
        services.setdefault(name, ServiceStatusView(age_seconds=None, status="UNAVAILABLE"))
    return SystemView(
        api="HEALTHY",
        database="HEALTHY",
        redis=redis_status,
        services=services,
        exchange="NOT_CONFIGURED",
        ai="DISABLED",
        telegram="ENABLED" if telegram_ready else "DISABLED",
        live_available=False,
    )


@router.get("/events", response_model=list[EventView])
async def events(request: Request, user: SignedIn) -> list[EventView]:
    async with request.app.state.sessions() as db:
        rows = (
            await db.scalars(
                select(EventRow).order_by(EventRow.timestamp.desc(), EventRow.id.desc()).limit(100)
            )
        ).all()
    return [
        EventView(id=row.id, timestamp=row.timestamp, event=row.event, message=row.message)
        for row in rows
    ]


@router.post("/control", response_model=ControlView)
async def control(body: ControlChange, request: Request, user: Admin) -> ControlView:
    async with request.app.state.sessions.begin() as db:
        row = await db.get(ControlRow, 1, with_for_update=True)
        if row is None:
            raise AuthError("System not initialized", 503)
        current = Control(Environment(row.environment), Status(row.status))
        changed = current.change(body.status, Role(user.role), body.environment)
        changed_state = row.status != changed.status or row.environment != changed.environment
        if changed_state:
            row.environment = changed.environment
            row.status = changed.status
            audit(db, "BOT_PAUSED" if changed.status == Status.PAUSED else "BOT_RESUMED", user.id)
    if changed_state:
        paused = changed.status == Status.PAUSED
        title = "Bot paused" if paused else "Bot resumed"
        severity = NotificationSeverity.WARNING if paused else NotificationSeverity.INFO
        await dispatch_telegram_notification(
            request.app.state.sessions,
            request.app.state.auth.crypto,
            request.app.state.telegram_transport,
            Notification(severity, title, f"Environment: {changed.environment}."),
        )
    return ControlView(status=changed.status, environment=changed.environment)
