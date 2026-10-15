"""Deliver compact, read-only Telegram digests of newly created AI proposals.

The job never calls an AI provider, execution path, wallet adapter, or Telegram command parser.
It only reads proposals already committed for one operator, sends one bounded summary through the
existing throttled notifier, and records its delivery watermark. Telegram remains informational:
the authenticated web UI is the sole decision surface.
"""

from datetime import datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.ai_autonomy import AiAutonomyStatus
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.infrastructure.ai_proposal_digest_repository import AiProposalDigestRepository
from wallybot.infrastructure.models import AiAutonomyControlRow, TradeProposalRow
from wallybot.notifications.telegram import Notification, NotificationSeverity, TelegramTransport
from wallybot.security.crypto import Crypto

MAX_PROPOSALS_PER_DIGEST = 5


def _proposal_line(row: TradeProposalRow, web_origin: str | None) -> str:
    action = "BUY / Comprar" if row.direction == "LONG" else "SELL / Vender"
    expires = row.as_of + timedelta(seconds=float(row.signal_ttl_seconds))
    line = (
        f"• {action} {row.base}/{row.quote} at {row.entry_price} ({float(row.confidence):.0%})"
        f"\n  Stop {row.stop_price or '—'} · TP {row.take_profit_price or '—'}"
        f" · expires / caduca {expires:%H:%M} UTC"
    )
    if web_origin:
        query = urlencode({"proposal": row.proposal_id, "decision": "approve"})
        line += f"\n  {web_origin.rstrip('/')}/intelligence?{query}#proposals"
    line += f"\n  /approve {row.proposal_id} MFA · /reject {row.proposal_id} MFA"
    return line


def _digest_notification(rows: list[TradeProposalRow], web_origin: str | None) -> Notification:
    body = (
        "New WallyBot analysis proposals / Nuevas propuestas de análisis:\n"
        + "\n".join(_proposal_line(row, web_origin) for row in rows)
        + "\n\nApprove or reject here replacing MFA with your 6-digit code, or open WallyBot. "
        "Aprobá o rechazá aquí cambiando MFA por tu código de 6 dígitos, o abrí WallyBot."
    )
    # Unique per batch so the notification throttle's (severity, title) dedup never hides one.
    newest = rows[0]
    return Notification(
        NotificationSeverity.INFO,
        f"New proposal / Nueva propuesta: {newest.base}/{newest.quote} {newest.as_of:%H:%M:%S}",
        body,
    )


async def run_ai_proposal_digest_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramTransport,
    throttle: NotificationThrottle,
    owner_id: str,
    now: datetime,
    immediate: bool = False,
    web_origin: str | None = None,
) -> bool:
    """Send unseen pending proposals: on the configured cadence, or right away when
    ``immediate`` -- proposals expire in minutes, so a delayed digest would arrive too late."""
    async with sessions() as db:
        control = await db.get(AiAutonomyControlRow, 1)
        if control is None or control.status != AiAutonomyStatus.ENABLED:
            return False
        watermark = await AiProposalDigestRepository(db).last_sent_at(owner_id)
        if (
            not immediate
            and watermark is not None
            and now - watermark < timedelta(hours=control.digest_interval_hours)
        ):
            return False
        query = (
            select(TradeProposalRow)
            .where(
                TradeProposalRow.owner_id == owner_id,
                TradeProposalRow.decision_status == "PENDING",
            )
            .order_by(TradeProposalRow.as_of.desc())
            .limit(MAX_PROPOSALS_PER_DIGEST)
        )
        if watermark is not None:
            query = query.where(TradeProposalRow.as_of > watermark)
        rows = list((await db.scalars(query)).all())
    # An expired proposal can no longer be approved; alerting it would only be noise.
    rows = [
        row for row in rows if row.as_of + timedelta(seconds=float(row.signal_ttl_seconds)) > now
    ]
    if not rows:
        return False

    await dispatch_telegram_notification(
        sessions, crypto, transport, _digest_notification(rows, web_origin), throttle, now
    )
    async with sessions.begin() as db:
        await AiProposalDigestRepository(db).mark_sent(owner_id, now)
    return True
