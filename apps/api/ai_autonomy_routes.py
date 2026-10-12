"""POST /api/ai-autonomy/control: the toggle for apps/ai_worker's periodic AI analysis.

Reuses the exact same Admin (ADMIN role + fresh MFA + throttle) dependency and row-locked
read-modify-write/audit/notify pattern apps/api/system_routes.py's own /control handler already
established -- no new auth code, per the build plan. Not part of the isolated research pipeline;
The worker only persists proposals; it cannot execute, transfer or withdraw. See ADR-017.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import AiAnalystAvailabilityView, AiAutonomyControlView
from apps.api.schemas import AiAutonomyChange
from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.ai_autonomy import AiAutonomyControl, AiAutonomyStatus
from wallybot.domain.control import Role
from wallybot.infrastructure.models import AiAnalystStatusRow, AiAutonomyControlRow
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.security.auth import AuthError, audit

router = APIRouter(prefix="/api", tags=["ai-autonomy"])

ANALYSTS = ("codex", "claude")


async def _analyst_availability(db) -> list[AiAnalystAvailabilityView]:
    """Report what the native worker observed; settings are never changed from this signal."""
    rows = {row.analyst: row for row in (await db.scalars(select(AiAnalystStatusRow))).all()}
    return [
        AiAnalystAvailabilityView(
            analyst=name,
            available=rows[name].available if name in rows else None,
            checked_at=(
                datetime.fromtimestamp(rows[name].checked_at, UTC) if name in rows else None
            ),
        )
        for name in ANALYSTS
    ]


@router.get("/ai-autonomy/control", response_model=AiAutonomyControlView)
async def get_ai_autonomy_control(request: Request, user: SignedIn) -> AiAutonomyControlView:
    async with request.app.state.sessions() as db:
        row = await db.get(AiAutonomyControlRow, 1)
        if row is None:
            raise AuthError("System not initialized", 503)
        return AiAutonomyControlView(
            status=AiAutonomyStatus(row.status),
            target_core_pct=row.target_core_pct,
            target_growth_pct=row.target_growth_pct,
            target_speculative_pct=row.target_speculative_pct,
            digest_interval_hours=row.digest_interval_hours,
            codex_enabled=row.codex_enabled,
            claude_enabled=row.claude_enabled,
            require_consensus=row.require_consensus,
            analysts=await _analyst_availability(db),
        )


@router.post("/ai-autonomy/control", response_model=AiAutonomyControlView)
async def change_ai_autonomy_control(
    body: AiAutonomyChange, request: Request, user: Admin
) -> AiAutonomyControlView:
    async with request.app.state.sessions.begin() as db:
        row = await db.get(AiAutonomyControlRow, 1, with_for_update=True)
        if row is None:
            raise AuthError("System not initialized", 503)
        current = AiAutonomyControl(
            status=AiAutonomyStatus(row.status),
            target_core_pct=row.target_core_pct,
            target_growth_pct=row.target_growth_pct,
            target_speculative_pct=row.target_speculative_pct,
            digest_interval_hours=row.digest_interval_hours,
            codex_enabled=row.codex_enabled,
            claude_enabled=row.claude_enabled,
            require_consensus=row.require_consensus,
        )
        try:
            changed = current.change(
                role=Role(user.role),
                status=body.status,
                target_core_pct=body.target_core_pct,
                target_growth_pct=body.target_growth_pct,
                target_speculative_pct=body.target_speculative_pct,
                digest_interval_hours=body.digest_interval_hours,
                codex_enabled=body.codex_enabled,
                claude_enabled=body.claude_enabled,
                require_consensus=body.require_consensus,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        changed_state = changed != current
        if changed_state:
            row.status = changed.status
            row.target_core_pct = changed.target_core_pct
            row.target_growth_pct = changed.target_growth_pct
            row.target_speculative_pct = changed.target_speculative_pct
            row.digest_interval_hours = changed.digest_interval_hours
            row.codex_enabled = changed.codex_enabled
            row.claude_enabled = changed.claude_enabled
            row.require_consensus = changed.require_consensus
            event = (
                "AI_AUTONOMY_ENABLED"
                if changed.status == AiAutonomyStatus.ENABLED
                else "AI_AUTONOMY_DISABLED"
            )
            audit(db, event, user.id)
        analysts = await _analyst_availability(db)
    if changed_state:
        enabled = changed.status == AiAutonomyStatus.ENABLED
        title = "AI proposal analysis enabled" if enabled else "AI proposal analysis disabled"
        severity = NotificationSeverity.WARNING if enabled else NotificationSeverity.INFO
        await dispatch_telegram_notification(
            request.app.state.sessions,
            request.app.state.auth.crypto,
            request.app.state.telegram_transport,
            Notification(severity, title, f"Status: {changed.status}."),
            request.app.state.notification_throttle,
            datetime.now(UTC),
        )
    return AiAutonomyControlView(
        status=changed.status,
        target_core_pct=changed.target_core_pct,
        target_growth_pct=changed.target_growth_pct,
        target_speculative_pct=changed.target_speculative_pct,
        digest_interval_hours=changed.digest_interval_hours,
        codex_enabled=changed.codex_enabled,
        claude_enabled=changed.claude_enabled,
        require_consensus=changed.require_consensus,
        analysts=analysts,
    )
