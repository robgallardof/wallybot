"""Deliver compact, read-only Telegram digests of newly created AI proposals.

The job never calls an AI provider, execution path, wallet adapter, or Telegram command parser.
It reads proposals already committed for one operator, sends ranked detailed cards through the
existing throttled notifier, and records its delivery watermark. Approval buttons are handled
separately by the allowlisted private-chat command loop.
"""

from dataclasses import replace
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.application.proposal_presentation import (
    display_context,
    proposal_notification,
    rank_proposals,
)
from wallybot.domain.ai_autonomy import AiAutonomyStatus
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.infrastructure.ai_proposal_digest_repository import AiProposalDigestRepository
from wallybot.infrastructure.models import AiAutonomyControlRow, TradeProposalRow
from wallybot.notifications.telegram import TelegramTransport
from wallybot.security.crypto import Crypto

MAX_PROPOSALS_PER_DIGEST = 5


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
            .limit(100)
        )
        if watermark is not None:
            query = query.where(TradeProposalRow.as_of > watermark)
        rows = list((await db.scalars(query)).all())
        context = await display_context(db, owner_id, now)
    # An expired proposal can no longer be approved; alerting it would only be noise.
    rows = [
        row for row in rows if row.as_of + timedelta(seconds=float(row.signal_ttl_seconds)) > now
    ]
    if not rows:
        return False

    rows = rank_proposals(rows, now)[:MAX_PROPOSALS_PER_DIGEST]
    for position, row in enumerate(rows, 1):
        notification = proposal_notification(row, position, context, now, web_origin=web_origin)
        # Include the stable ID in the title so deduplication does not hide a new proposal.
        notification = replace(notification, title=f"{notification.title} · {row.proposal_id}")
        await dispatch_telegram_notification(
            sessions, crypto, transport, notification, throttle, now
        )
    async with sessions.begin() as db:
        await AiProposalDigestRepository(db).mark_sent(owner_id, now)
    return True
