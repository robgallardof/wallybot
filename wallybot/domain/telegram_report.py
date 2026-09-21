"""Pure content assembly for the daily/weekly Telegram report (PENDING.md Fase 8: "Generar
reportes diarios/semanales con rendimiento neto, costes, benchmarks, riesgos y problemas de
servicio.").

No I/O here -- `wallybot.application.telegram_report_job` fetches everything this module needs
(equity snapshots, fees, active breakers, heartbeats) and this module only turns already-fetched
values into report text. Kept in the domain layer, like `wallybot.domain.breaker`'s pure latch
logic, and for the same reason `wallybot.domain.notification_throttle` stays here rather than
importing `wallybot.notifications.telegram`: domain code depends on nothing outward
(ARCHITECTURE.md's Ports & Adapters), so `ReportSeverity` mirrors `NotificationSeverity`'s values
instead of importing it, and the application layer converts one to the other.

"Benchmarks" (BTC/ETH/cash passive comparison) is explicitly **not** implemented anywhere in this
codebase yet -- that is PENDING.md Fase 5's still-unchecked "Comparar BTC, ETH, efectivo y
portafolio pasivo." This module states that plainly in the report body rather than fabricating a
number; never remove that line without actually implementing the comparison first.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.breaker import Breaker, BreakerType


class ReportPeriod(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class ReportSeverity(StrEnum):
    """Same three values as `wallybot.notifications.telegram.NotificationSeverity`, duplicated
    here so this module never imports that adapter-layer type -- see module docstring."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class EquityWindow:
    """`None` means "no equity snapshot exists for that point" -- never fabricated as zero.

    :ivar starting_equity: Equity at (or first snapshot after) the period's start, if any.
    :ivar current_equity: The latest known equity, if any.
    """

    starting_equity: Decimal | None
    current_equity: Decimal | None

    @property
    def return_pct(self) -> Decimal | None:
        """Percent return over the window, or `None` if either side is missing or a starting
        equity of zero would make the ratio meaningless."""
        if self.starting_equity is None or self.current_equity is None:
            return None
        if self.starting_equity == 0:
            return None
        return (self.current_equity - self.starting_equity) / self.starting_equity * Decimal(100)


@dataclass(frozen=True)
class ServiceHeartbeat:
    """:ivar age_seconds: `None` means no heartbeat row exists for `service` at all, distinct
    from a heartbeat that merely aged past the staleness threshold."""

    service: str
    age_seconds: int | None
    stale: bool


@dataclass(frozen=True)
class ReportInputs:
    period: ReportPeriod
    environment: str
    period_start: datetime
    now: datetime
    equity: EquityWindow
    total_fees: Decimal
    active_breakers: tuple[Breaker, ...]
    heartbeats: tuple[ServiceHeartbeat, ...]


@dataclass(frozen=True)
class ReportContent:
    severity: ReportSeverity
    title: str
    body: str


_PERIOD_LABEL = {ReportPeriod.DAILY: "Daily", ReportPeriod.WEEKLY: "Weekly"}


def build_report_content(inputs: ReportInputs) -> ReportContent:
    """Turn `inputs` into the report's title/body/severity. Pure function of its argument."""
    lines = [
        f"Window: {inputs.period_start.isoformat()} to {inputs.now.isoformat()} "
        f"({inputs.environment})",
        "",
        "Equity/PnL:",
    ]
    if inputs.equity.starting_equity is None or inputs.equity.current_equity is None:
        lines.append("  No equity snapshot recorded for this period yet.")
    else:
        pct = inputs.equity.return_pct
        pct_suffix = f" ({pct:+.2f}%)" if pct is not None else ""
        lines.append(
            f"  Start {inputs.equity.starting_equity} -> "
            f"Current {inputs.equity.current_equity}{pct_suffix}"
        )

    lines += ["", f"Costs: {inputs.total_fees} in fees this period."]

    lines += ["", "Risk:"]
    if inputs.active_breakers:
        for breaker in inputs.active_breakers:
            lines.append(f"  {breaker.breaker_type.value}: {breaker.reason}")
    else:
        lines.append("  No active breakers.")
    reconciliation_breaker = next(
        (b for b in inputs.active_breakers if b.breaker_type is BreakerType.RECONCILIATION),
        None,
    )
    lines.append(
        "  Reconciliation: "
        + (
            f"DEGRADED -- {reconciliation_breaker.reason}"
            if reconciliation_breaker is not None
            else "healthy"
        )
    )

    lines += ["", "Service health:"]
    stale_services = []
    for heartbeat in inputs.heartbeats:
        status = "STALE" if heartbeat.stale else "HEALTHY"
        age = (
            "no heartbeat received"
            if heartbeat.age_seconds is None
            else f"{heartbeat.age_seconds}s ago"
        )
        lines.append(f"  {heartbeat.service}: {status} ({age})")
        if heartbeat.stale:
            stale_services.append(heartbeat.service)

    lines += [
        "",
        "Benchmarks: not available -- BTC/ETH/cash passive comparison is not implemented yet "
        "(PENDING.md Fase 5).",
    ]

    if reconciliation_breaker is not None:
        severity = ReportSeverity.CRITICAL
    elif inputs.active_breakers or stale_services:
        severity = ReportSeverity.WARNING
    else:
        severity = ReportSeverity.INFO

    title = f"{_PERIOD_LABEL[inputs.period]} report -- {inputs.now.date().isoformat()}"
    return ReportContent(severity=severity, title=title, body="\n".join(lines))
