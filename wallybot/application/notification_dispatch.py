"""Sends an outbound :class:`Notification` through Telegram, if and only if an operator has
configured and enabled one -- otherwise a silent no-op, never a required dependency.

This lives next to the other application-layer orchestrators (``research_runner.py``,
``market_ingestion.py``) because it composes a domain-agnostic notifier with infrastructure
(the encrypted config row, the crypto instance) the way they compose their own ports. Only
``apps/api`` currently calls this: it is the sole backend process on a Docker network with
internet egress (``worker``/``scheduler``/``research`` are ``internal: true``, per PENDING.md's
Fase 7 network isolation), so this cannot run from a scheduler/worker tick yet.

Every call is gated by a :class:`~wallybot.domain.notification_throttle.NotificationThrottle`
(PENDING.md Fase 8: "Integrar notificaciones por severidad, agrupación, deduplicación y límites
para evitar spam.") -- an identical severity+title pair within its dedup window, or more than its
hourly cap of sends, is silently dropped before ever reaching the Telegram transport. The
dedup/rate-limit decision itself is pure and lives in the domain module; this function only
consults it around the existing config-lookup-then-send flow.
"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.infrastructure.telegram_config_repository import TelegramConfigRepository
from wallybot.notifications.telegram import Notification, TelegramNotifier, TelegramTransport
from wallybot.security.crypto import Crypto

logger = logging.getLogger("wallybot")


async def dispatch_telegram_notification(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramTransport,
    notification: Notification,
    throttle: NotificationThrottle,
    now: datetime,
) -> None:
    """Best-effort delivery of ``notification`` to the operator's configured Telegram chat.

    :param sessions: Session factory used for a short read of the singleton Telegram config row.
    :param crypto: Decrypts the stored bot token; never logged, never returned to a caller.
    :param transport: HTTP transport the notifier sends through; see :class:`TelegramTransport`.
    :param notification: The message to send; see :class:`Notification`.
    :param throttle: Dedup/rate-limit guard shared across every call in the process; see
        :class:`~wallybot.domain.notification_throttle.NotificationThrottle`.
    :param now: Current time, used only for the throttle decision; timezone-aware.
    :returns: ``None`` always. A missing/disabled config, a throttled send, a decrypt failure, or
        a delivery failure are all logged (``TELEGRAM_NOTIFICATION_SKIPPED``/
        ``TELEGRAM_NOTIFICATION_SUPPRESSED``/``TELEGRAM_NOTIFICATION_FAILED``) and swallowed --
        Telegram is a convenience channel, never a dependency of the action that triggered the
        notification.
    """
    async with sessions() as db:
        config = await TelegramConfigRepository(db).get()
    if config is None or not config.enabled or not config.encrypted_bot_token:
        return
    chat_id = config.chat_id
    if chat_id is None:
        return
    if not throttle.should_send(notification.severity.value, notification.title, now):
        logger.info(
            "TELEGRAM_NOTIFICATION_SUPPRESSED",
            extra={"severity": notification.severity.value, "title": notification.title},
        )
        return
    throttle.record(notification.severity.value, notification.title, now)
    try:
        token = crypto.decrypt(config.encrypted_bot_token)
        notifier = TelegramNotifier(token, frozenset({chat_id}), transport)
        await notifier.notify(chat_id, notification)
    except Exception:
        logger.warning("TELEGRAM_NOTIFICATION_FAILED")
