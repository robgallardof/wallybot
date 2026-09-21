"""Long-polls Telegram's `getUpdates` for inbound commands from the operator's single allowlisted
chat (SECURITY.md: "allowlisted numeric user/chat IDs"). Query commands (`/status`, `/breakers`,
`/portfolio`) reply immediately with a snapshot; sensitive commands (`/pause`, `/resume`) never
execute directly -- they create a `wallybot.domain.telegram_confirmation.TelegramConfirmation` the
operator must confirm through the existing Admin+fresh-MFA web flow, and reply saying so.
`/help`/`/commands` (also `/start`, once already paired -- Telegram's own convention for a bot's
entry point) list every recognized command with a one-line description. Every reply is in English
or Spanish, resolved per-message from Telegram's own `message.from.language_code`
(`wallybot.notifications.telegram_i18n.resolve_language`) -- there is no stored language
preference, since the sender's own Telegram client already reports it on every message.

Only `apps/api` calls this: same "sole process with internet egress" constraint as
`price_consensus_job`/`notification_dispatch`. `apps/api/main.py`'s `_telegram_command_loop`
wrapper resolves the current admin/account each tick and passes it in here, matching
`decision_loop.run_decision_tick`'s own split (DB-admin-lookup stays in the apps/api wrapper,
never imported down into this application-layer module).

`GET_UPDATES_TIMEOUT_SECONDS` (8s) is deliberately well under the shared `HttpxTelegramTransport`
client's own 10s request timeout (`apps/api/main.py`'s lifespan) -- Telegram's long-poll `timeout`
param holds the HTTP response open until either an update arrives or that many seconds pass, and a
value at or above the client's own timeout would make httpx raise a read timeout before Telegram
ever replies.
"""

import hmac
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.telegram_commands import TelegramCommand, parse_command
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.telegram_confirmation import CONFIRMATION_TTL, TelegramAction
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.models import ControlRow
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.telegram_confirmation_repository import TelegramConfirmationRepository
from wallybot.notifications.telegram import TelegramCommandTransport
from wallybot.notifications.telegram_i18n import Language, resolve_language
from wallybot.security.crypto import Crypto, digest

GET_UPDATES_TIMEOUT_SECONDS = 8


async def run_telegram_command_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramCommandTransport,
    id_generator: IdGenerator,
    account_id: str | None,
    now: datetime,
) -> None:
    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    if config is None or not config.encrypted_bot_token:
        return

    # Before a destination is known, long-poll only to process an exact one-time /start pairing
    # code. No command is ever executed in this state and arbitrary chats receive no response.
    if config.chat_id is None:
        if config.pairing_code_hash is None:
            return
        await _run_pairing_tick(sessions, crypto, transport, config, now)
        return

    if not config.enabled:
        return

    token = crypto.decrypt(config.encrypted_bot_token)
    base_url = f"https://api.telegram.org/bot{token}"
    params = {"timeout": str(GET_UPDATES_TIMEOUT_SECONDS)}
    if config.last_update_id is not None:
        params["offset"] = str(config.last_update_id + 1)
    payload = await transport.get_json(f"{base_url}/getUpdates", params)
    updates = payload.get("result", [])
    if not updates:
        return

    max_update_id = max(update["update_id"] for update in updates)

    # First-ever poll after enabling: only establish the cursor, never execute a backlog of
    # messages that predate this integration (e.g. an old "/pause" sent before Telegram commands
    # existed) as if it were just issued.
    if config.last_update_id is not None:
        for update in updates:
            message = update.get("message")
            if not message or "text" not in message or "chat" not in message:
                continue
            chat_id = message["chat"]["id"]
            if chat_id != config.chat_id:
                continue  # not the allowlisted chat -- ignored, never replied to
            language = resolve_language((message.get("from") or {}).get("language_code"))
            reply = await _handle_command(
                sessions, account_id, id_generator, now, message["text"], language
            )
            if reply is not None:
                await transport.post_form(
                    f"{base_url}/sendMessage", {"chat_id": str(chat_id), "text": reply}
                )

    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(max_update_id)


async def _run_pairing_tick(
    sessions: async_sessionmaker[AsyncSession], crypto: Crypto, transport: TelegramCommandTransport,
    config, now: datetime,
) -> None:
    token = crypto.decrypt(config.encrypted_bot_token)
    base_url = f"https://api.telegram.org/bot{token}"
    params = {"timeout": str(GET_UPDATES_TIMEOUT_SECONDS)}
    if config.last_update_id is not None:
        params["offset"] = str(config.last_update_id + 1)
    payload = await transport.get_json(f"{base_url}/getUpdates", params)
    updates = payload.get("result", [])
    if not updates:
        return
    max_update_id = max(update["update_id"] for update in updates)
    for update in updates:
        message = update.get("message")
        if not message or "text" not in message or "chat" not in message:
            continue
        supplied = _pairing_code(message["text"])
        if supplied is None or not hmac.compare_digest(digest(supplied), config.pairing_code_hash):
            continue
        chat_id = message["chat"]["id"]
        language = resolve_language((message.get("from") or {}).get("language_code"))
        async with sessions.begin() as db:
            paired = await TelegramConfigRepository(db).complete_pairing(chat_id, max_update_id)
        if paired:
            text = (
                "WallyBot linked. Alerts and secure commands are ready now."
                if language == "en"
                else "WallyBot vinculado. Las alertas y comandos seguros ya están listos."
            )
            await transport.post_form(
                f"{base_url}/sendMessage", {"chat_id": str(chat_id), "text": text}
            )
        return
    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(max_update_id)


def _pairing_code(text: str) -> str | None:
    parts = text.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].split("@", 1)[0] != "/start":
        return None
    code = parts[1].strip()
    valid_characters = all(
        char.isascii() and (char.isalnum() or char in "_-") for char in code
    )
    if not (1 <= len(code) <= 64) or not valid_characters:
        return None
    return code


async def _handle_command(
    sessions: async_sessionmaker[AsyncSession],
    account_id: str | None,
    id_generator: IdGenerator,
    now: datetime,
    text: str,
    language: Language,
) -> str | None:
    command = parse_command(text)
    if command is None:
        return None
    if command is TelegramCommand.STATUS:
        return await _status_reply(sessions, language)
    if command is TelegramCommand.BREAKERS:
        return await _breakers_reply(sessions, language)
    if command is TelegramCommand.PORTFOLIO:
        return await _portfolio_reply(sessions, account_id, language)
    if command is TelegramCommand.HELP:
        return _help_reply(language)
    action = TelegramAction.PAUSE if command is TelegramCommand.PAUSE else TelegramAction.RESUME
    return await _confirmation_reply(sessions, id_generator, now, action, language)


def _help_reply(language: Language) -> str:
    if language == "en":
        return (
            "Available commands:\n"
            "/status -- environment and status (RUNNING/PAUSED)\n"
            "/breakers -- active circuit breakers\n"
            "/portfolio -- latest equity snapshot\n"
            "/pause -- request a pause (confirm on the web with MFA)\n"
            "/resume -- request a resume (confirm on the web with MFA)\n"
            "/help -- this message"
        )
    return (
        "Comandos disponibles:\n"
        "/status -- entorno y estado (RUNNING/PAUSED)\n"
        "/breakers -- circuit breakers activos\n"
        "/portfolio -- último snapshot de equity\n"
        "/pause -- solicita pausar (confirmás en la web con MFA)\n"
        "/resume -- solicita reanudar (confirmás en la web con MFA)\n"
        "/help -- este mensaje"
    )


async def _status_reply(sessions: async_sessionmaker[AsyncSession], language: Language) -> str:
    async with sessions() as db:
        row = await db.get(ControlRow, 1)
    if row is None:
        return "System not initialized." if language == "en" else "Sistema no inicializado."
    if language == "en":
        return f"Environment: {row.environment}\nStatus: {row.status}"
    return f"Entorno: {row.environment}\nEstado: {row.status}"


async def _breakers_reply(sessions: async_sessionmaker[AsyncSession], language: Language) -> str:
    async with sessions() as db:
        active = await BreakerRepository(db).list_active()
    if not active:
        return "No active breakers." if language == "en" else "Sin breakers activos."
    lines = [f"{breaker.breaker_type.value}: {breaker.reason}" for breaker in active]
    header = "Active breakers:" if language == "en" else "Breakers activos:"
    return header + "\n" + "\n".join(lines)


async def _portfolio_reply(
    sessions: async_sessionmaker[AsyncSession], account_id: str | None, language: Language
) -> str:
    if account_id is None:
        return (
            "Portfolio unavailable: no administrator configured."
            if language == "en"
            else "Portafolio no disponible: no hay administrador configurado."
        )
    async with sessions() as db:
        snapshot = await EquitySnapshotRepository(db).latest(account_id, "PAPER")
    if snapshot is None:
        return (
            "No equity snapshot yet."
            if language == "en"
            else "Todavía no hay un snapshot de equity."
        )
    if language == "en":
        return (
            f"Equity: {snapshot.equity} (as of {snapshot.recorded_at.isoformat()})\n"
            f"High-water mark: {snapshot.high_water_mark}"
        )
    return (
        f"Equity: {snapshot.equity} (al {snapshot.recorded_at.isoformat()})\n"
        f"High-water mark: {snapshot.high_water_mark}"
    )


async def _confirmation_reply(
    sessions: async_sessionmaker[AsyncSession],
    id_generator: IdGenerator,
    now: datetime,
    action: TelegramAction,
    language: Language,
) -> str:
    target_status = Status.PAUSED if action is TelegramAction.PAUSE else Status.RUNNING
    async with sessions() as db:
        control_row = await db.get(ControlRow, 1)
    if control_row is not None and Status(control_row.status) == target_status:
        return (
            f"Already in {target_status.value} state."
            if language == "en"
            else f"Ya está en estado {target_status.value}."
        )
    async with sessions.begin() as db:
        await TelegramConfirmationRepository(db).create(action, now, id_generator)
    minutes = int(CONFIRMATION_TTL / timedelta(minutes=1))
    if language == "en":
        return (
            f"{action.value} request registered. Confirm it on the web (Settings) within "
            f"{minutes} minutes with your MFA session -- Telegram cannot execute it on its own."
        )
    return (
        f"Solicitud de {action.value} registrada. Confírmala en la web (Configuración) "
        f"dentro de {minutes} minutos con tu sesión MFA -- "
        "Telegram no puede ejecutarla por sí solo."
    )
