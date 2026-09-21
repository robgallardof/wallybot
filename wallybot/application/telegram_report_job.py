"""Assembles and sends the daily/weekly Telegram report (PENDING.md Fase 8: "Generar reportes
diarios/semanales con rendimiento neto, costes, benchmarks, riesgos y problemas de servicio.").

Wired as `_telegram_report_loop` in `apps/api/main.py`, same split as `_telegram_command_loop`/
`run_telegram_command_tick`: this module resolves data via repositories and composes
`wallybot.domain.telegram_report`'s pure content builder with `dispatch_telegram_notification`,
and the loop wrapper only resolves "which account" and paces the tick.

"Already sent today/this week" is tracked in `telegram_reports` (migration 0031) rather than
recomputed from other history, so a crash mid-tick never causes a resend once the process
restarts and the loop's next tick lands within the same day/week. `mark_sent` is called once per
period per tick unconditionally -- even if Telegram is not configured/enabled (in which case
`dispatch_telegram_notification` itself is a no-op) -- because the marker's job is only to pace
report *generation* to once per period, the same "convenience channel, never a dependency"
posture `dispatch_telegram_notification` already documents for delivery itself. Handling a
genuine delivery failure so it is retried is PENDING.md Fase 8's still-unchecked "Manejar fallos
de entrega sin alterar verdad financiera" item, not this one.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.domain.notification_throttle import NotificationThrottle
from wallybot.domain.telegram_report import (
    EquityWindow,
    ReportInputs,
    ReportPeriod,
    ReportSeverity,
    ServiceHeartbeat,
    build_report_content,
)
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.models import HeartbeatRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.telegram_report_repository import TelegramReportRepository
from wallybot.notifications.telegram import Notification, NotificationSeverity, TelegramTransport
from wallybot.security.crypto import Crypto

# Matches apps/api/system_routes.py's /api/system route exactly -- a heartbeat older than this is
# STALE there, and the report must agree with what the dashboard already shows for the same data.
HEARTBEAT_STALE_SECONDS = 30
HEARTBEAT_SERVICES = ("api", "worker", "scheduler", "research")

_SEVERITY_MAP = {
    ReportSeverity.INFO: NotificationSeverity.INFO,
    ReportSeverity.WARNING: NotificationSeverity.WARNING,
    ReportSeverity.CRITICAL: NotificationSeverity.CRITICAL,
}


def _period_start(period: ReportPeriod, now: datetime) -> datetime:
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period is ReportPeriod.DAILY:
        return start_of_day
    return start_of_day - timedelta(days=start_of_day.weekday())  # Monday 00:00 UTC


def _period_key(period: ReportPeriod, now: datetime) -> str:
    if period is ReportPeriod.DAILY:
        return now.date().isoformat()
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _heartbeat_status(
    service: str, timestamp: int | None, now: datetime
) -> ServiceHeartbeat:
    if timestamp is None:
        return ServiceHeartbeat(service=service, age_seconds=None, stale=True)
    age = max(0, int(now.timestamp()) - timestamp)
    return ServiceHeartbeat(service=service, age_seconds=age, stale=age >= HEARTBEAT_STALE_SECONDS)


async def _build_inputs(
    db: AsyncSession, period: ReportPeriod, account_id: str, environment: str, now: datetime
) -> ReportInputs:
    period_start = _period_start(period, now)
    equity_repo = EquitySnapshotRepository(db)
    current = await equity_repo.latest(account_id, environment)
    window_snapshots = await equity_repo.recent(account_id, environment, period_start)
    starting = window_snapshots[0] if window_snapshots else None

    total_fees = await PortfolioRepository(db).sum_fees_since(account_id, period_start)
    active_breakers = await BreakerRepository(db).list_active()

    beat_rows = (await db.scalars(select(HeartbeatRow))).all()
    beats = {beat.service: beat.timestamp for beat in beat_rows}
    heartbeats = tuple(
        _heartbeat_status(service, beats.get(service), now) for service in HEARTBEAT_SERVICES
    )

    return ReportInputs(
        period=period,
        environment=environment,
        period_start=period_start,
        now=now,
        equity=EquityWindow(
            starting_equity=starting.equity if starting is not None else None,
            current_equity=current.equity if current is not None else None,
        ),
        total_fees=total_fees,
        active_breakers=active_breakers,
        heartbeats=heartbeats,
    )


async def run_telegram_report_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    transport: TelegramTransport,
    throttle: NotificationThrottle,
    account_id: str,
    environment: str,
    now: datetime,
) -> None:
    """For each of DAILY/WEEKLY: if this period's report was not already generated (by its own
    `last_sent_key`), build it from real data and dispatch it over Telegram.

    :param account_id: The single PAPER account this system administers (PENDING.md Fase 1: no
        multi-user account administration yet).
    :param environment: Passed through to the equity/fee queries; "PAPER" in production today.
    :param now: Current time; timezone-aware, drives both period-window math and the throttle.
    """
    for period in (ReportPeriod.DAILY, ReportPeriod.WEEKLY):
        key = _period_key(period, now)
        async with sessions() as db:
            already_sent = await TelegramReportRepository(db).last_sent_key(period.value)
        if already_sent == key:
            continue

        async with sessions() as db:
            inputs = await _build_inputs(db, period, account_id, environment, now)
        content = build_report_content(inputs)
        notification = Notification(_SEVERITY_MAP[content.severity], content.title, content.body)
        await dispatch_telegram_notification(
            sessions, crypto, transport, notification, throttle, now
        )

        async with sessions.begin() as db:
            await TelegramReportRepository(db).mark_sent(period.value, key, now)
