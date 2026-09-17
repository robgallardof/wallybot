"""Lets an operator store their own Telegram bot token (from @BotFather) and destination chat.

This route only owns safe storage and status reporting: the bot token is never returned once
set, only whether one is present. Actually sending a message is triggered elsewhere -- see
``wallybot.application.notification_dispatch``, called so far only from the control-plane route
(``apps/api/system_routes.py``'s ``control()``), since ``apps/api`` is the only backend process
with internet egress (``worker``/``scheduler``/``research`` are network-isolated, per
PENDING.md's Fase 7).
"""

from fastapi import APIRouter, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import TelegramConfigView
from apps.api.schemas import TelegramConfigUpdate
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def _view(row) -> TelegramConfigView:
    return TelegramConfigView(
        has_bot_token=bool(row and row.encrypted_bot_token),
        chat_id=row.chat_id if row else None,
        enabled=bool(row and row.enabled),
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
    async with request.app.state.sessions.begin() as db:
        row = await TelegramConfigRepository(db).upsert(encrypted, body.chat_id, body.enabled)
        result = _view(row)
    return result
