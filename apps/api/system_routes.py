import csv
import io
import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_, or_, select, text

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import (
    AuditEventView,
    ControlView,
    DashboardView,
    EventPageView,
    EventView,
    ServiceStatusView,
    SystemView,
)
from apps.api.schemas import ControlChange
from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.control import Control, Environment, Role, Status
from wallybot.infrastructure.metrics import SERVICE_HEARTBEAT_AGE
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
    for name, view in services.items():
        if view.age_seconds is not None:
            SERVICE_HEARTBEAT_AGE.labels(name).set(view.age_seconds)
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


def _parse_event_cursor(cursor: str) -> tuple[int, str]:
    # Cursor is "<timestamp>:<id>", the same (timestamp, id) tuple the listing orders and
    # tie-breaks by. EventRow.id is a uuid4 string, which never contains ":", so a simple
    # partition is safe -- no need for base64/opaque encoding of what isn't secret anyway.
    timestamp_part, separator, id_part = cursor.partition(":")
    if not separator or not id_part:
        raise HTTPException(status_code=400, detail="Invalid cursor")
    try:
        return int(timestamp_part), id_part
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor") from None


@router.get("/events", response_model=EventPageView)
async def events(
    request: Request,
    user: SignedIn,
    before: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    q: str | None = None,
    event: str | None = None,
) -> EventPageView:
    # Cursor pagination over an append-only, monotonically growing table: unlike offset
    # pagination, a page never drifts when new events are inserted concurrently. EventRow.id has
    # no natural ordering (it's a uuid4), so (timestamp, id) is the tie-break for the rare case
    # multiple events share the same integer `timestamp` second.
    conditions = []
    if before is not None:
        cursor_timestamp, cursor_id = _parse_event_cursor(before)
        conditions.append(
            or_(
                EventRow.timestamp < cursor_timestamp,
                and_(EventRow.timestamp == cursor_timestamp, EventRow.id < cursor_id),
            )
        )
    if event:
        conditions.append(EventRow.event == event)
    if q:
        pattern = f"%{q}%"
        conditions.append(or_(EventRow.event.ilike(pattern), EventRow.message.ilike(pattern)))

    stmt = select(EventRow).order_by(EventRow.timestamp.desc(), EventRow.id.desc()).limit(limit + 1)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    async with request.app.state.sessions() as db:
        rows = (await db.scalars(stmt)).all()

    has_more = len(rows) > limit
    page = rows[:limit]
    next_before = f"{page[-1].timestamp}:{page[-1].id}" if has_more and page else None
    return EventPageView(
        rows=[
            EventView(id=row.id, timestamp=row.timestamp, event=row.event, message=row.message)
            for row in page
        ],
        next_before=next_before,
    )


# A safety cap, not a business limit -- same reasoning as portfolio_routes.py's EXPORT_FILL_LIMIT.
EXPORT_EVENT_LIMIT = 50_000
_AUDIT_EXPORT_FIELDNAMES: tuple[str, ...] = (
    "id",
    "timestamp",
    "actor",
    "event",
    "message",
    "correlation_id",
)


@router.get("/events/export")
async def export_events(
    request: Request,
    user: SignedIn,
    format: Literal["csv", "json"] = "csv",
    since: int | None = None,
    until: int | None = None,
) -> Response:
    """Export the audit trail as CSV or JSON -- unlike `events()`, includes `actor` and
    `correlation_id`, withheld from the regular paginated feed but exactly what a compliance
    export needs. Same authentication as the regular feed (`SignedIn`): this is a read of data
    every signed-in user can already page through one screen at a time, just bulk and complete
    instead. `since`/`until` (Unix seconds, inclusive) optionally scope the export to a window;
    unset means the most recent `EXPORT_EVENT_LIMIT` rows.
    """
    conditions = []
    if since is not None:
        conditions.append(EventRow.timestamp >= since)
    if until is not None:
        conditions.append(EventRow.timestamp <= until)
    stmt = (
        select(EventRow)
        .order_by(EventRow.timestamp.desc(), EventRow.id.desc())
        .limit(EXPORT_EVENT_LIMIT)
    )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    async with request.app.state.sessions() as db:
        rows = (await db.scalars(stmt)).all()

    export_rows = [
        AuditEventView(
            id=row.id,
            timestamp=datetime.fromtimestamp(row.timestamp, UTC).isoformat(),
            actor=row.actor,
            event=row.event,
            message=row.message,
            correlation_id=row.correlation_id,
        )
        for row in rows
    ]

    if format == "json":
        return JSONResponse(
            [row.model_dump() for row in export_rows],
            headers={"Content-Disposition": 'attachment; filename="wallybot-audit-log.json"'},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_AUDIT_EXPORT_FIELDNAMES)
    writer.writeheader()
    writer.writerows(row.model_dump() for row in export_rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="wallybot-audit-log.csv"'},
    )


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
            request.app.state.notification_throttle,
            datetime.now(UTC),
        )
    return ControlView(status=changed.status, environment=changed.environment)
