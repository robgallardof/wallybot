"""Deliver compact, read-only Telegram digests of newly created AI proposals.

The job never calls an AI provider, execution path, wallet adapter, or Telegram command parser.
It only reads proposals already committed for one operator, sends one bounded summary through the
existing throttled notifier, and records its delivery watermark. Telegram remains informational:
the authenticated web UI is the sole decision surface.
"""

from datetime import datetime, timedelta

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


def _digest_notification(rows: list[TradeProposalRow]) -> Notification:
    lines = [
        f"• {'BUY' if row.direction == 'LONG' else 'SELL'} {row.base}/{row.quote} "
        f"/ {'Comprar' if row.direction == 'LONG' else 'Vender'} at {row.entry_price} "
        f"({float(row.confidence):.0%})"
        for row in rows
    ]
    body = (
        "New WallyBot analysis proposals / Nuevas propuestas de análisis:\n"
        + "\n".join(lines)
        + "\n\nOpen WallyBot to review, approve or reject with MFA. "
        "Abrí WallyBot para revisar, aprobar o rechazar con MFA."
    )
    return Notification(
        NotificationSeverity.INFO,
        "WallyBot analysis digest / Resumen de análisis",
        body,
    )


async def run_ai_proposal_digest_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramTransport,
    throttle: NotificationThrottle,
    owner_id: str,
    now: datetime,
) -> bool:
    """Send at most one configured-cadence digest when unseen pending proposals exist."""
    async with sessions() as db:
        control = await db.get(AiAutonomyControlRow, 1)
        if control is None or control.status != AiAutonomyStatus.ENABLED:
            return False
        watermark = await AiProposalDigestRepository(db).last_sent_at(owner_id)
        if watermark is not None and now - watermark < timedelta(
            hours=control.digest_interval_hours
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
    if not rows:
        return False

    await dispatch_telegram_notification(
        sessions, crypto, transport, _digest_notification(rows), throttle, now
    )
    async with sessions.begin() as db:
        await AiProposalDigestRepository(db).mark_sent(owner_id, now)
    return True
