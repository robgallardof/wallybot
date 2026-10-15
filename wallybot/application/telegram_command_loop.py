"""Long-polls Telegram's `getUpdates` for inbound commands from the operator's single allowlisted
chat (SECURITY.md: "allowlisted numeric user/chat IDs"). Query commands (`/status`, `/breakers`,
`/portfolio`, `/proposals`, `/withdrawal`) reply immediately with read-only evidence; sensitive
commands (`/pause`, `/resume`) never
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
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.paper_accounts import paper_ai_account_id
from wallybot.application.portfolio_performance import compute_fifo_performance
from wallybot.application.telegram_commands import TelegramCommand, parse_command
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.telegram_confirmation import CONFIRMATION_TTL, TelegramAction
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.models import ControlRow, TradeProposalRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
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
    owner_id: str | None = None,
    web_origin: str | None = None,
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
                sessions,
                account_id,
                owner_id,
                id_generator,
                now,
                message["text"],
                language,
                web_origin,
            )
            if reply is not None:
                await transport.post_form(
                    f"{base_url}/sendMessage", {"chat_id": str(chat_id), "text": reply}
                )

    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(max_update_id)


async def _run_pairing_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramCommandTransport,
    config,
    now: datetime,
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
    valid_characters = all(char.isascii() and (char.isalnum() or char in "_-") for char in code)
    if not (1 <= len(code) <= 64) or not valid_characters:
        return None
    return code


async def _handle_command(
    sessions: async_sessionmaker[AsyncSession],
    account_id: str | None,
    owner_id: str | None,
    id_generator: IdGenerator,
    now: datetime,
    text: str,
    language: Language,
    web_origin: str | None = None,
) -> str | None:
    command = parse_command(text)
    if command is None:
        return None
    if command in {TelegramCommand.APPROVE, TelegramCommand.REJECT, TelegramCommand.SIMULATE}:
        return await _proposal_review_reply(
            sessions, owner_id, now, text, command, language, web_origin
        )
    if command is TelegramCommand.STATUS:
        return await _status_reply(sessions, language)
    if command is TelegramCommand.BREAKERS:
        return await _breakers_reply(sessions, language)
    if command is TelegramCommand.PORTFOLIO:
        return await _portfolio_reply(sessions, account_id, owner_id, language)
    if command is TelegramCommand.PROPOSALS:
        return await _proposals_reply(sessions, owner_id, language)
    if command is TelegramCommand.WITHDRAWAL:
        return await _withdrawal_reply(sessions, owner_id, language)
    if command is TelegramCommand.HELP:
        return _help_reply(language)
    action = TelegramAction.PAUSE if command is TelegramCommand.PAUSE else TelegramAction.RESUME
    return await _confirmation_reply(sessions, id_generator, now, action, language)


async def _proposal_review_reply(
    sessions: async_sessionmaker[AsyncSession],
    owner_id: str | None,
    now: datetime,
    text: str,
    command: TelegramCommand,
    language: Language,
    web_origin: str | None,
) -> str:
    """Create a navigation link only; the authenticated web decision is always separate."""
    parts = text.split()
    if len(parts) != 2 or re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", parts[1]) is None:
        return (
            "Use /approve ID, /reject ID or /simulate ID from /proposals. Confirm in WallyBot."
            if language == "en"
            else "Usá /approve ID, /reject ID o /simulate ID de /proposals. Confirmá en WallyBot."
        )
    async with sessions() as db:
        row = (
            await db.scalar(
                select(TradeProposalRow).where(
                    TradeProposalRow.proposal_id == parts[1],
                    TradeProposalRow.owner_id == owner_id,
                )
            )
            if owner_id is not None
            else None
        )
    if row is None or row.decision_status != "PENDING":
        return "Proposal unavailable." if language == "en" else "Propuesta no disponible."
    expires = row.as_of + timedelta(seconds=float(row.signal_ttl_seconds))
    if now >= expires and command is not TelegramCommand.REJECT:
        return "Proposal expired." if language == "en" else "La propuesta caducó."
    query = urlencode({"proposal": row.proposal_id, "decision": command.value.lower()})
    link = f"{web_origin.rstrip('/')}/intelligence?{query}#proposals" if web_origin else "WallyBot"
    return (
        f"Review {command.value}: {row.base}/{row.quote} at {row.entry_price}. "
        f"Nothing was approved or executed. Open the link, review and confirm with MFA:\n{link}"
        if language == "en"
        else f"Revisar {command.value}: {row.base}/{row.quote} a {row.entry_price}. "
        f"No se aprobó ni ejecutó nada. Abrí el enlace, revisá y confirmá con MFA:\n{link}"
    )


def _help_reply(language: Language) -> str:
    if language == "en":
        return (
            "Available commands:\n"
            "/status -- environment and status (RUNNING/PAUSED)\n"
            "/breakers -- active circuit breakers\n"
            "/portfolio -- latest equity snapshot\n"
            "/proposals -- latest AI proposals (read-only)\n"
            "/approve ID /reject ID /simulate ID -- open a web review with MFA\n"
            "/withdrawal -- informational realized-result review (read-only)\n"
            "/pause -- request a pause (confirm on the web with MFA)\n"
            "/resume -- request a resume (confirm on the web with MFA)\n"
            "/help -- this message"
        )
    return (
        "Comandos disponibles:\n"
        "/status -- entorno y estado (RUNNING/PAUSED)\n"
        "/breakers -- circuit breakers activos\n"
        "/portfolio -- último snapshot de equity\n"
        "/proposals -- últimas propuestas de IA (solo lectura)\n"
        "/approve ID /reject ID /simulate ID -- abrir revisión web con MFA\n"
        "/withdrawal -- revisión informativa de resultado realizado (solo lectura)\n"
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
    sessions: async_sessionmaker[AsyncSession],
    account_id: str | None,
    owner_id: str | None,
    language: Language,
) -> str:
    from wallybot.infrastructure.live_models import LiveControlRow
    from wallybot.infrastructure.models import ProviderConnectionRow

    async with sessions() as db:
        live = await db.get(LiveControlRow, 1)
        if live is not None and live.owner_id == owner_id:
            snapshot = await EquitySnapshotRepository(db).latest(
                "live:" + live.connection_id, "LIVE"
            )
            if snapshot is not None:
                connection = await db.get(ProviderConnectionRow, live.connection_id)
                venue = connection.provider.title() if connection is not None else "Unknown"
                currency = "USDT" if venue == "Binance" else "USD"
                return (
                    f"LIVE · {venue} spot · {live.state}\nEquity: {snapshot.equity} {currency} "
                    f"({snapshot.recorded_at.isoformat()})\n{live.reason}\n"
                    + (
                        "Initial holdings have unknown historical cost. No withdrawal capability."
                        if language == "en"
                        else (
                            "El coste hist\u00f3rico de las posiciones iniciales no se conoce. "
                            "No se pueden retirar fondos."
                        )
                    )
                )
    ai_summary = await _ai_portfolio_summary(sessions, owner_id, language)
    if account_id is None:
        return (
            "Portfolio unavailable: no administrator configured.\n" + ai_summary
            if language == "en"
            else "Portafolio no disponible: no hay administrador configurado.\n" + ai_summary
        )
    async with sessions() as db:
        snapshot = await EquitySnapshotRepository(db).latest(account_id, "PAPER")
    if snapshot is None:
        return (
            "No equity snapshot yet.\n" + ai_summary
            if language == "en"
            else "Todavía no hay un snapshot de equity.\n" + ai_summary
        )
    if language == "en":
        return (
            f"Equity: {snapshot.equity} (as of {snapshot.recorded_at.isoformat()})\n"
            f"High-water mark: {snapshot.high_water_mark}\n{ai_summary}"
        )
    return (
        f"Equity: {snapshot.equity} (al {snapshot.recorded_at.isoformat()})\n"
        f"High-water mark: {snapshot.high_water_mark}\n{ai_summary}"
    )


async def _ai_portfolio_summary(
    sessions: async_sessionmaker[AsyncSession], owner_id: str | None, language: Language
) -> str:
    """Return only confirmed AI PAPER facts for the already-authorized Telegram chat."""
    if owner_id is None:
        return (
            "AI account: unavailable (no administrator configured)."
            if language == "en"
            else "Cuenta IA: no disponible (no hay administrador configurado)."
        )
    async with sessions() as db:
        fills = await PortfolioRepository(db).list_recent_fills(
            paper_ai_account_id(owner_id), limit=50_000
        )
    if not fills:
        return (
            "AI account: no confirmed operations yet."
            if language == "en"
            else "Cuenta IA: aún no hay operaciones confirmadas."
        )
    try:
        performance = compute_fifo_performance(reversed(fills))
    except ValueError:
        return (
            f"AI account: {len(fills)} confirmed fills; "
            "reconciliation required for realized result."
            if language == "en"
            else f"Cuenta IA: {len(fills)} fills confirmados; "
            "se requiere conciliación para el resultado realizado."
        )
    realized = ", ".join(
        f"{item.realized_pnl:+} {item.quote}" for item in performance if item.realized_pnl != 0
    )
    if not realized:
        realized = "none yet" if language == "en" else "sin resultado realizado aún"
    if language == "en":
        return f"AI account: {len(fills)} confirmed fills · realized: {realized}."
    return f"Cuenta IA: {len(fills)} fills confirmados · realizado: {realized}."


async def _proposals_reply(
    sessions: async_sessionmaker[AsyncSession], owner_id: str | None, language: Language
) -> str:
    if owner_id is None:
        return (
            "Proposals unavailable: no administrator configured."
            if language == "en"
            else "Propuestas no disponibles: no hay administrador configurado."
        )
    async with sessions() as db:
        rows = (
            await db.scalars(
                select(TradeProposalRow)
                .where(TradeProposalRow.owner_id == owner_id)
                .order_by(TradeProposalRow.as_of.desc())
                .limit(5)
            )
        ).all()
    if not rows:
        return "No AI proposals yet." if language == "en" else "Todavía no hay propuestas de IA."

    def execution_context(row: TradeProposalRow) -> str:
        if row.execution_status is None:
            return ""
        return f" · {row.execution_environment or 'PAPER'} {row.execution_status}"

    if language == "en":
        lines = ["Latest AI proposals:"]
        lines.extend(
            f"{row.proposal_id}: {row.direction} {row.base}/{row.quote} "
            f"at {row.entry_price} — {row.decision_status}{execution_context(row)}"
            for row in rows
        )
        return "\n".join(lines) + "\nOpen WallyBot to simulate, approve, or reject with MFA."
    lines = ["Últimas propuestas de IA:"]
    lines.extend(
        f"{row.proposal_id}: {row.direction} {row.base}/{row.quote} "
        f"a {row.entry_price} — {row.decision_status}{execution_context(row)}"
        for row in rows
    )
    return "\n".join(lines) + "\nAbrí WallyBot para simular, aprobar o rechazar con MFA."


async def _withdrawal_reply(
    sessions: async_sessionmaker[AsyncSession], owner_id: str | None, language: Language
) -> str:
    """Summarize confirmed results without exposing any fund-movement surface.

    A recommendation is deliberately conservative: it can only describe realized FIFO results in
    the AI PAPER ledger. It never receives a destination, builds an order, creates a confirmation,
    or calls an exchange/provider.
    """
    if owner_id is None:
        return (
            "Withdrawal review unavailable: no administrator configured."
            if language == "en"
            else "Revisión de retiro no disponible: no hay administrador configurado."
        )
    async with sessions() as db:
        fills = await PortfolioRepository(db).list_recent_fills(
            paper_ai_account_id(owner_id), limit=50_000
        )
    if not fills:
        return (
            "No confirmed AI operations yet; there is no withdrawal review. "
            "WallyBot cannot move funds."
            if language == "en"
            else "Aún no hay operaciones de IA confirmadas; no hay revisión de retiro. "
            "WallyBot no puede mover fondos."
        )
    try:
        performance = compute_fifo_performance(reversed(fills))
    except ValueError:
        return (
            "Withdrawal review unavailable: the confirmed ledger needs reconciliation. "
            "WallyBot cannot move funds."
            if language == "en"
            else "Revisión de retiro no disponible: el libro confirmado necesita conciliación. "
            "WallyBot no puede mover fondos."
        )
    realized = [item for item in performance if item.realized_pnl != 0]
    if not realized:
        return (
            "No realized AI result to review yet. This command cannot withdraw or transfer funds."
            if language == "en"
            else "Todavía no hay resultado realizado de IA para revisar. "
            "Este comando no puede retirar ni transferir fondos."
        )
    values = ", ".join(f"{item.realized_pnl:+} {item.quote}" for item in realized)
    if language == "en":
        return (
            f"Informational realized result: {values}. "
            "Review it in WallyBot before making any external decision. "
            "WallyBot cannot withdraw, transfer, receive a destination, or approve a movement."
        )
    return (
        f"Resultado realizado informativo: {values}. "
        "Revisalo en WallyBot antes de cualquier decisión externa. "
        "WallyBot no puede retirar, transferir, recibir un destino ni aprobar un movimiento."
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
