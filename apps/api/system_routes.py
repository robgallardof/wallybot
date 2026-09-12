import time

from fastapi import APIRouter, Request
from sqlalchemy import select, text

from apps.api.dependencies import Admin, SignedIn
from apps.api.schemas import ControlChange
from wallybot.domain.control import Control, Role, Status
from wallybot.infrastructure.models import ControlRow, EventRow, HeartbeatRow
from wallybot.security.auth import AuthError, audit

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/dashboard")
async def dashboard(request: Request, user: SignedIn) -> dict[str, object]:
    async with request.app.state.sessions() as db:
        state = await db.get(ControlRow, 1)
        if state is None:
            raise AuthError("System not initialized", 503)
        return {
            "environment": state.environment,
            "status": state.status,
            "trading_available": False,
            "exchange": "NOT_CONFIGURED",
            "equity": None,
            "positions": [],
            "phase": 1,
        }


@router.get("/system")
async def system(request: Request, user: SignedIn) -> dict[str, object]:
    async with request.app.state.sessions() as db:
        await db.execute(text("SELECT 1"))
        beats = (await db.scalars(select(HeartbeatRow))).all()
    redis_status = "HEALTHY"
    try:
        await request.app.state.redis.ping()
    except Exception:
        redis_status = "UNAVAILABLE"
    now = int(time.time())
    services = {
        beat.service: {
            "age_seconds": max(0, now - beat.timestamp),
            "status": "HEALTHY" if 0 <= now - beat.timestamp < 30 else "STALE",
        }
        for beat in beats
    }
    for name in ("worker", "scheduler", "research"):
        services.setdefault(name, {"age_seconds": None, "status": "UNAVAILABLE"})
    return {
        "api": "HEALTHY",
        "database": "HEALTHY",
        "redis": redis_status,
        "services": services,
        "exchange": "NOT_CONFIGURED",
        "ai": "DISABLED",
        "telegram": "DISABLED",
        "live_available": False,
    }


@router.get("/events")
async def events(request: Request, user: SignedIn) -> list[dict[str, object]]:
    async with request.app.state.sessions() as db:
        rows = (
            await db.scalars(
                select(EventRow).order_by(EventRow.timestamp.desc(), EventRow.id.desc()).limit(100)
            )
        ).all()
    return [
        {"id": row.id, "timestamp": row.timestamp, "event": row.event, "message": row.message}
        for row in rows
    ]


@router.post("/control")
async def control(body: ControlChange, request: Request, user: Admin) -> dict[str, str]:
    async with request.app.state.sessions.begin() as db:
        row = await db.get(ControlRow, 1, with_for_update=True)
        if row is None:
            raise AuthError("System not initialized", 503)
        current = Control(row.environment, Status(row.status))
        changed = current.change(body.status, Role(user.role))
        if row.status != changed.status:
            row.status = changed.status
            audit(db, "BOT_PAUSED" if changed.status == Status.PAUSED else "BOT_RESUMED", user.id)
    return {"status": changed.status, "environment": changed.environment}
