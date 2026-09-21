"""Lets an operator store their own Telegram bot token (from @BotFather) and destination chat.

This route only owns safe storage and status reporting: the bot token is never returned once
set, only whether one is present. Actually sending a message is triggered elsewhere -- see
``wallybot.application.notification_dispatch``, called so far only from the control-plane route
(``apps/api/system_routes.py``'s ``control()``), since ``apps/api`` is the only backend process
with internet egress (``worker``/``scheduler``/``research`` are network-isolated, per
PENDING.md's Fase 7).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import TelegramConfigView, TelegramConfirmationListView, TelegramConfirmationView
from apps.api.schemas import TelegramConfigUpdate
from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.control import Control, Environment, Role, Status
from wallybot.domain.telegram_confirmation import TelegramAction
from wallybot.infrastructure.models import ControlRow
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.telegram_confirmation_repository import TelegramConfirmationRepository
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.security.auth import AuthError, audit
from wallybot.security.crypto import digest, token

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def _view(row, pairing_code: str | None = None) -> TelegramConfigView:
    pairing_status = (
        "NEEDS_TOKEN"
        if row is None or not row.encrypted_bot_token
        else "LINKED"
        if row.chat_id is not None
        else "WAITING_FOR_START"
    )
    return TelegramConfigView(
        has_bot_token=bool(row and row.encrypted_bot_token),
        chat_id=row.chat_id if row else None,
        enabled=bool(row and row.enabled),
        pairing_status=pairing_status,
        pairing_code=pairing_code,
    )


@router.get("", response_model=TelegramConfigView)
async def get_telegram_config(request: Request, user: SignedIn) -> TelegramConfigView:
    async with request.app.state.sessions() as db:
        row = await TelegramConfigRepository(db).get()
    return _view(row)


@router.post("", response_model=TelegramConfigView)
async def set_telegram_config(
    body: TelegramConfigUpdate, request: Request, user: Admin
) -> TelegramConfigView:
    crypto = request.app.state.auth.crypto
    encrypted = crypto.encrypt(body.bot_token) if body.bot_token else None
    # A token has no safe destination until the owner proves control of the destination chat by
    # sending the fresh, browser-only code to that bot. Never auto-allowlist the first sender.
    begin_pairing = body.start_pairing or (bool(body.bot_token) and body.chat_id is None)
    if begin_pairing and encrypted is None:
        async with request.app.state.sessions() as db:
            existing = await TelegramConfigRepository(db).get()
        if existing is None or not existing.encrypted_bot_token:
            raise HTTPException(status_code=409, detail="Save a bot token before starting pairing")
    pairing_code = token() if begin_pairing else None
    async with request.app.state.sessions.begin() as db:
        row = await TelegramConfigRepository(db).upsert(
            encrypted,
            body.chat_id,
            body.enabled,
            pairing_code_hash=digest(pairing_code) if pairing_code else None,
            begin_pairing=begin_pairing,
        )
        result = _view(row, pairing_code)
    return result


def _confirmation_view(confirmation) -> TelegramConfirmationView:
    return TelegramConfirmationView(
        confirmation_id=confirmation.confirmation_id,
        action=confirmation.action.value,
        requested_at=confirmation.requested_at.isoformat(),
        expires_at=confirmation.expires_at.isoformat(),
        confirmed_at=confirmation.confirmed_at.isoformat() if confirmation.confirmed_at else None,
        confirmed_by=confirmation.confirmed_by,
    )


@router.get("/confirmations", response_model=TelegramConfirmationListView)
async def list_confirmations(request: Request, user: SignedIn) -> TelegramConfirmationListView:
    async with request.app.state.sessions() as db:
        rows = await TelegramConfirmationRepository(db).list_pending(datetime.now(UTC))
    return TelegramConfirmationListView(rows=[_confirmation_view(row) for row in rows])


@router.post("/confirmations/{confirmation_id}/confirm", response_model=TelegramConfirmationView)
async def confirm_telegram_confirmation(
    confirmation_id: str, request: Request, user: Admin
) -> TelegramConfirmationView:
    now = datetime.now(UTC)
    async with request.app.state.sessions.begin() as db:
        repo = TelegramConfirmationRepository(db)
        pending = await repo.get(confirmation_id)
        if pending is None:
            raise HTTPException(status_code=404, detail="Unknown confirmation")
        confirmed = await repo.confirm(confirmation_id, user.id, now)
        if not confirmed:
            raise HTTPException(status_code=409, detail="Confirmation is no longer pending")

        control_row = await db.get(ControlRow, 1, with_for_update=True)
        if control_row is None:
            raise AuthError("System not initialized", 503)
        current = Control(Environment(control_row.environment), Status(control_row.status))
        target_status = (
            Status.PAUSED if pending.action == TelegramAction.PAUSE else Status.RUNNING
        )
        changed = current.change(target_status, Role(user.role))
        changed_state = control_row.status != changed.status
        if changed_state:
            control_row.status = changed.status
            audit(db, "BOT_PAUSED" if changed.status == Status.PAUSED else "BOT_RESUMED", user.id)
        audit(db, "TELEGRAM_CONFIRMATION_CONFIRMED", user.id)

    if changed_state:
        await dispatch_telegram_notification(
            request.app.state.sessions,
            request.app.state.auth.crypto,
            request.app.state.telegram_transport,
            Notification(
                NotificationSeverity.INFO,
                "Confirmado desde la web",
                f"{pending.action.value} confirmado por {user.id}.",
            ),
            request.app.state.notification_throttle,
            now,
        )

    async with request.app.state.sessions() as db:
        result = await TelegramConfirmationRepository(db).get(confirmation_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Confirmation vanished after confirming")
    return _confirmation_view(result)
