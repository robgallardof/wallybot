"""Long-polls Telegram's `getUpdates` for inbound commands from the operator's single allowlisted
chat (SECURITY.md: "allowlisted numeric user/chat IDs"). Query commands (`/status`, `/breakers`,
`/portfolio`, `/proposals`, `/withdrawal`) reply immediately with read-only evidence.
`/approve ID`, `/reject ID` and inline buttons record decisions through the injected callback
only from the linked private operator chat, without per-decision MFA. The shared decision path
retains ownership, expiry, mode binding and deterministic risk revalidation. Sensitive commands
(`/pause`, `/resume`) never
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
import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.paper_accounts import paper_ai_account_id
from wallybot.application.portfolio_performance import compute_fifo_performance
from wallybot.application.proposal_presentation import (
    display_context,
    proposal_notification,
    rank_proposals,
)
from wallybot.application.telegram_commands import TelegramCommand, parse_command
from wallybot.domain.control import Status
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import MarketDataProvider
from wallybot.domain.telegram_confirmation import CONFIRMATION_TTL, TelegramAction
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.live_models import AnalystPortfolioRow, LiveControlRow
from wallybot.infrastructure.models import AiAutonomyControlRow, ControlRow, TradeProposalRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.infrastructure.telegram_confirmation_repository import TelegramConfirmationRepository
from wallybot.notifications.telegram import Notification, TelegramCommandTransport
from wallybot.notifications.telegram_i18n import Language, resolve_language
from wallybot.security.crypto import Crypto, digest

GET_UPDATES_TIMEOUT_SECONDS = 8

# (proposal_id, decision, optional displayed mode/version binding) -> decision result.
# Throttling and refused decisions are reported to the operator.
ProposalDecider = Callable[[str, str, str | None], Awaitable[dict[str, str | None]]]


async def run_telegram_command_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramCommandTransport,
    id_generator: IdGenerator,
    account_id: str | None,
    now: datetime,
    owner_id: str | None = None,
    web_origin: str | None = None,
    decide: ProposalDecider | None = None,
    market: MarketDataProvider | None = None,
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
    params = {
        "timeout": str(GET_UPDATES_TIMEOUT_SECONDS),
        "allowed_updates": json.dumps(["message", "callback_query"]),
    }
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
            callback = update.get("callback_query")
            if callback is not None:
                await _handle_callback(callback, config.chat_id, decide, transport, base_url)
                continue
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
                decide if _private_operator(message, config.chat_id) else None,
                market,
            )
            if reply is not None:
                replies = reply if isinstance(reply, list) else [reply]
                for item in replies:
                    form = {
                        "chat_id": str(chat_id),
                        "text": item.text if isinstance(item, Notification) else item,
                    }
                    if isinstance(item, Notification) and item.reply_markup is not None:
                        form["reply_markup"] = json.dumps(item.reply_markup)
                    await transport.post_form(f"{base_url}/sendMessage", form)

    async with sessions.begin() as db:
        await TelegramConfigRepository(db).set_last_update_id(max_update_id)


def _private_operator(message: dict, chat_id: int) -> bool:
    chat, sender = message.get("chat") or {}, message.get("from") or {}
    return (
        chat.get("type") == "private"
        and chat.get("id") == chat_id
        and sender.get("id") == chat_id
        and not sender.get("is_bot", False)
    )


async def _handle_callback(
    callback: dict,
    chat_id: int,
    decide: ProposalDecider | None,
    transport: TelegramCommandTransport,
    base_url: str,
) -> None:
    message = callback.get("message") or {}
    message = {**message, "from": callback.get("from") or {}}
    language = resolve_language(message["from"].get("language_code"))
    en = language == "en"
    if not _private_operator(message, chat_id) or decide is None:
        reply = "Use your linked private chat." if en else "Usa tu chat privado vinculado."
    else:
        match = re.fullmatch(
            r"(approve|reject):([A-Za-z0-9_-]{1,64}):(OBSERVE|PAPER|LIVE):(\d{1,10})",
            str(callback.get("data", "")),
        )
        if match is None:
            reply = "Invalid button. Use /proposals." if en else "Botón no válido. Usa /proposals."
        else:
            decision, proposal_id, environment, version = match.groups()
            await transport.post_form(
                f"{base_url}/answerCallbackQuery",
                {
                    "callback_query_id": str(callback["id"]),
                    "text": "Processing…" if en else "Procesando…",
                },
            )
            reply = await _decision_reply(
                decide,
                proposal_id,
                TelegramCommand(decision.upper()),
                f"{environment}:{version}",
                language,
            )
            await transport.post_form(
                f"{base_url}/sendMessage",
                {
                    "chat_id": str(chat_id),
                    "text": reply,
                },
            )
            return
    await transport.post_form(
        f"{base_url}/answerCallbackQuery",
        {
            "callback_query_id": str(callback["id"]),
            "text": reply[:180],
            "show_alert": "true",
        },
    )


async def _run_pairing_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramCommandTransport,
    config,
    now: datetime,
) -> None:
    token = crypto.decrypt(config.encrypted_bot_token)
    base_url = f"https://api.telegram.org/bot{token}"
    params = {
        "timeout": str(GET_UPDATES_TIMEOUT_SECONDS),
        "allowed_updates": json.dumps(["message", "callback_query"]),
    }
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
    decide: ProposalDecider | None = None,
    market: MarketDataProvider | None = None,
) -> str | list[Notification] | None:
    command = parse_command(text)
    if command is None:
        return None
    parts = text.split()
    if (
        decide is not None
        and command in {TelegramCommand.APPROVE, TelegramCommand.REJECT}
        and len(parts) == 2
        and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", parts[1])
    ):
        return await _decision_reply(decide, parts[1], command, None, language)
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
        return await _proposals_reply(sessions, owner_id, language, now, web_origin)
    if command is TelegramCommand.WITHDRAWAL:
        return await _withdrawal_reply(sessions, owner_id, language)
    if command is TelegramCommand.HELP:
        return _help_reply(language)
    if command is TelegramCommand.INIT:
        return await _init_reply(sessions, language)
    if command is TelegramCommand.ANALYZE:
        return await _analyze_reply(sessions, owner_id, now, language, market)
    action = TelegramAction.PAUSE if command is TelegramCommand.PAUSE else TelegramAction.RESUME
    return await _confirmation_reply(sessions, id_generator, now, action, language)


async def _decision_reply(
    decide: ProposalDecider,
    proposal_id: str,
    command: TelegramCommand,
    binding: str | None,
    language: Language,
) -> str:
    try:
        result = await decide(proposal_id, command.value.lower(), binding)
    except Exception as exc:  # noqa: BLE001 -- every refusal is reported, nothing is retried
        detail = getattr(exc, "detail", None) or getattr(exc, "message", None) or str(exc)
        reason = str(detail) or type(exc).__name__
        return f"Not recorded: {reason}" if language == "en" else f"No se registró: {reason}"
    status, execution = result.get("status"), result.get("execution_status")
    reason = result.get("execution_reason")
    explanation = f"\n{reason}" if reason else ""
    if language == "en":
        reply = f"Proposal {status}."
        return reply + (f" Execution: {execution}." if execution else "") + explanation
    reply = {"APPROVED": "Propuesta aprobada.", "REJECTED": "Propuesta rechazada."}.get(
        str(status), f"Propuesta {status}."
    )
    return reply + (f" Ejecución: {execution}." if execution else "") + explanation


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
            "Use /approve ID or /reject ID in your linked private chat, or /simulate ID "
            "from /proposals."
            if language == "en"
            else "Usa /approve ID o /reject ID en tu chat privado vinculado, o "
            "/simulate ID de /proposals."
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


async def _init_reply(sessions: async_sessionmaker[AsyncSession], language: Language) -> str:
    """Ask the analysts for one starter buy; it is only a proposal, approval stays on the web."""
    async with sessions.begin() as db:
        row = await db.get(AiAutonomyControlRow, 1, with_for_update=True)
        if row is None or row.status != "ENABLED":
            return (
                "AI analysis is disabled. Enable it in WallyBot first."
                if language == "en"
                else "El análisis IA está desactivado. Activalo primero en WallyBot."
            )
        row.starter_requested = True
    return (
        "Starter analysis requested. Codex and Claude will look for one conservative first buy "
        "within a minute; if they agree you will get a proposal to approve here. "
        "Nothing is executed automatically."
        if language == "en"
        else "Análisis inicial solicitado. Codex y Claude buscarán una primera compra "
        "conservadora en el próximo minuto; si se ponen de acuerdo te llegará una propuesta "
        "para aprobar aquí. No se ejecuta nada automáticamente."
    )


async def _analyze_reply(
    sessions: async_sessionmaker[AsyncSession],
    owner_id: str | None,
    now: datetime,
    language: Language,
    market: MarketDataProvider | None,
) -> str:
    """Show what is held (entry, time held, result) and ask the analysts to review it now.

    Any resulting SELL/BUY is an ordinary proposal, sent with its approve/reject buttons."""
    en = language == "en"
    async with sessions.begin() as db:
        portfolio = await db.get(AnalystPortfolioRow, owner_id) if owner_id else None
        live = await db.get(LiveControlRow, 1)
        control = await db.get(AiAutonomyControlRow, 1, with_for_update=True)
        holdings = (
            {asset: Decimal(quantity) for asset, quantity in (portfolio.holdings or {}).items()}
            if portfolio
            else {}
        )
        ai_enabled = control is not None and control.status == "ENABLED"
        # The AI worker refuses LIVE context older than a minute, so a stale snapshot is not
        # worth a review request (it would only fire later, unexpectedly).
        fresh = portfolio is not None and now - portfolio.as_of <= timedelta(seconds=60)
        if ai_enabled and holdings and fresh:
            control.review_requested = True
    if portfolio is None:
        return (
            "No real-account snapshot yet. Activate LIVE in WallyBot first."
            if en
            else "Todavía no hay datos de la cuenta real. Activa LIVE primero en WallyBot."
        )
    quote = "USDT" if portfolio.venue == "binance" else "USD"
    prices = await _current_prices(market, portfolio.venue, quote, holdings)
    lines = [
        ("Your positions" if en else "Tus posiciones")
        + f" ({portfolio.venue.title()} · {portfolio.as_of:%Y-%m-%d %H:%M} UTC):"
    ]
    for asset, quantity in sorted(holdings.items()):
        price = prices.get(asset)
        facts = (portfolio.positions or {}).get(asset)
        parts = [f"• {asset}: {quantity.normalize():f}"]
        if facts:
            entry = Decimal(facts["average_price"])
            held = now - datetime.fromisoformat(facts["held_since"])
            parts.append(("avg entry " if en else "entrada media ") + f"{entry:.6g} {quote}")
            parts.append(f"{held.days} d {held.seconds // 3600} h")
            if price:
                parts.append(f"{price / entry - 1:+.2%}")
        else:
            parts.append(
                "bought outside WallyBot (entry unknown)"
                if en
                else "comprado fuera de WallyBot (entrada desconocida)"
            )
        if price:
            parts.append(("now " if en else "ahora ") + f"{price:.6g}")
            parts.append(("value " if en else "valor ") + f"{quantity * price:.2f} {quote}")
        lines.append(" · ".join(parts))
    if not holdings:
        lines.append("No open positions." if en else "Sin posiciones abiertas.")
    lines.append(("Cash" if en else "Efectivo") + f": {portfolio.cash_usd:.2f} {quote}")
    if not fresh:
        state = f"{live.state}: {live.reason}" if live is not None else "OFF"
        lines.append(
            f"⚠️ Data is stale; LIVE is {state}\nNo AI review until LIVE is READY again."
            if en
            else f"⚠️ Datos desactualizados; LIVE está {state}\n"
            "Los analistas no pueden revisar hasta que LIVE vuelva a READY."
        )
    elif not ai_enabled:
        lines.append(
            "AI analysis is disabled; enable it in WallyBot for a recommendation."
            if en
            else "El análisis IA está desactivado; actívalo en WallyBot para tener recomendación."
        )
    elif holdings:
        lines.append(
            "Codex and Claude are reviewing each position now. If they recommend selling or "
            "adding, you will get a proposal here with buttons to approve; no proposal means "
            "they recommend holding. Nothing is executed automatically."
            if en
            else "Codex y Claude están revisando cada posición ahora. Si recomiendan vender o "
            "aumentar, te llega aquí la propuesta con botones para aprobar; si no llega "
            "ninguna, recomiendan mantener. No se ejecuta nada automáticamente."
        )
    return "\n".join(lines)


async def _current_prices(
    market: MarketDataProvider | None, venue: str, quote: str, holdings: dict[str, Decimal]
) -> dict[str, Decimal]:
    """Best-effort bid per held asset; a missing quote only hides that asset's value."""
    if market is None or not holdings:
        return {}
    prices = {}
    try:
        instruments = await market.discover_instruments()
    except Exception:  # noqa: BLE001 -- prices are optional in this reply
        return {}
    for instrument in instruments:
        if instrument.venue == venue and instrument.quote == quote and instrument.base in holdings:
            try:
                prices[instrument.base] = (await market.fetch_snapshot(instrument)).bid
            except Exception:  # noqa: BLE001
                continue
    return prices


def _help_reply(language: Language) -> str:
    if language == "en":
        return (
            "Available commands:\n"
            "/status -- environment and status (RUNNING/PAUSED)\n"
            "/breakers -- active circuit breakers\n"
            "/portfolio -- latest equity snapshot\n"
            "/proposals -- latest AI proposals (read-only)\n"
            "/approve ID /reject ID -- decide in your linked private chat, no MFA\n"
            "/simulate ID -- open a web simulation review\n"
            "/init -- ask the analysts for a first conservative buy (approve here)\n"
            "/analyze -- review what you hold: entry, time held, result; hold or sell proposals\n"
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
        "/approve ID /reject ID -- decidir en tu chat privado vinculado, sin MFA\n"
        "/simulate ID -- abrir revisión de simulación web\n"
        "/init -- pide a los analistas una primera compra conservadora (apruebas aquí)\n"
        "/analyze -- revisa lo que tienes: entrada, tiempo, resultado; propone vender o mantener\n"
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
    sessions: async_sessionmaker[AsyncSession],
    owner_id: str | None,
    language: Language,
    now: datetime,
    web_origin: str | None = None,
) -> str | list[Notification]:
    if owner_id is None:
        return "Proposals unavailable." if language == "en" else "Propuestas no disponibles."
    async with sessions() as db:
        rows = list(
            (
                await db.scalars(
                    select(TradeProposalRow)
                    .where(TradeProposalRow.owner_id == owner_id)
                    .order_by(TradeProposalRow.as_of.desc())
                    .limit(100)
                )
            ).all()
        )
        context = await display_context(db, owner_id, now)
    if not rows:
        return "No AI proposals yet." if language == "en" else "Todavía no hay propuestas de IA."
    return [
        proposal_notification(row, i, context, now, language, web_origin)
        for i, row in enumerate(rank_proposals(rows, now)[:5], 1)
    ]


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
