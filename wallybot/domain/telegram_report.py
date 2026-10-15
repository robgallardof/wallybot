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

Unavailable comparisons are stated without invented values or internal roadmap labels.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from wallybot.domain.benchmarks import MarketBenchmarks
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
    currency: str = "USD"
    venue: str | None = None
    language: Literal["en", "es"] = "en"
    reconciliation_state: str | None = None
    equity_as_of: datetime | None = None
    benchmarks: MarketBenchmarks | None = None


@dataclass(frozen=True)
class ReportContent:
    severity: ReportSeverity
    title: str
    body: str


_PERIOD_LABEL = {ReportPeriod.DAILY: "Daily", ReportPeriod.WEEKLY: "Weekly"}


def build_report_content(inputs: ReportInputs) -> ReportContent:
    """Build an account-unit report without treating missing evidence as verified health."""
    spanish = inputs.language == "es"

    def label(en: str, es: str) -> str:
        return es if spanish else en

    lines = [
        label("Window", "Periodo")
        + f": {inputs.period_start.isoformat()} → {inputs.now.isoformat()}",
        label("Mode", "Modo") + f": {inputs.environment}",
        label("Currency", "Moneda") + f": {inputs.currency}",
    ]
    if inputs.venue is not None:
        lines.append(label("Exchange", "Exchange") + f": {inputs.venue.title()}")
    lines += ["", label("Account value:", "Valor de la cuenta:")]
    if inputs.equity.starting_equity is None or inputs.equity.current_equity is None:
        lines.append(
            label(
                "  No equity snapshot recorded for this period yet.",
                "  No hay una valoración registrada para este periodo.",
            )
        )
    else:
        pct = inputs.equity.return_pct
        suffix = f" ({pct:+.2f}%)" if pct is not None else ""
        lines.append(
            label("  Start", "  Inicial")
            + f" {inputs.equity.starting_equity} → "
            + label("Current", "Actual")
            + f" {inputs.equity.current_equity} {inputs.currency}{suffix}"
        )
        lines.append(
            label(
                "  Value change; not a cash-flow-adjusted investment return.",
                "  Variación de valor; no es rentabilidad ajustada por movimientos de fondos.",
            )
        )
    if inputs.equity_as_of is not None:
        lines.append(
            label("  Last valuation", "  Última valoración")
            + f": {inputs.equity_as_of.isoformat()}"
        )
    lines += [
        "",
        label("Costs", "Costes")
        + f": {inputs.total_fees} {inputs.currency} "
        + label("in fees this period.", "en comisiones del periodo."),
    ]
    lines += ["", label("Risk:", "Riesgo:")]
    for breaker in inputs.active_breakers:
        lines.append(f"  {breaker.breaker_type.value}: {breaker.reason}")
    if not inputs.active_breakers:
        lines.append(label("  No active breakers.", "  Sin bloqueos de riesgo activos."))
    reconciliation = next(
        (b for b in inputs.active_breakers if b.breaker_type is BreakerType.RECONCILIATION), None
    )
    if reconciliation is not None:
        state = f"DEGRADED -- {reconciliation.reason}"
    else:
        states = {
            "READY": label("verified", "verificada"),
            "BLOCKED": label("blocked", "bloqueada"),
            "STALE": label("stale; verification required", "desactualizada; requiere verificación"),
        }
        state = states.get(inputs.reconciliation_state or "") or label(
            "not verified; no exchange reconciliation evidence",
            "no verificada; sin evidencia de conciliación del exchange",
        )
    lines.append(label("  Reconciliation: ", "  Conciliación: ") + state)
    lines += ["", label("Service health:", "Servicios:")]
    stale_services = []
    for heartbeat in inputs.heartbeats:
        status = label("STALE", "DESACTUALIZADO") if heartbeat.stale else label("HEALTHY", "ACTIVO")
        age = (
            label("no heartbeat received", "sin señal de actividad")
            if heartbeat.age_seconds is None
            else f"{heartbeat.age_seconds}s"
        )
        lines.append(f"  {heartbeat.service}: {status} ({age})")
        if heartbeat.stale:
            stale_services.append(heartbeat.service)
    benchmarks = inputs.benchmarks
    if (
        benchmarks is None
        or benchmarks.currency != inputs.currency
        or benchmarks.end > inputs.now
        or (inputs.venue is not None and benchmarks.venue != inputs.venue)
    ):
        lines += [
            "",
            label(
                "Benchmarks: not available for BTC/ETH/cash; "
                "matching closed-price evidence is missing.",
                "Referencias BTC/ETH/efectivo: no disponibles; faltan cierres comparables.",
            ),
        ]
    else:
        lines += [
            "",
            label("Gross market references", "Referencias de mercado brutas")
            + f" ({benchmarks.venue.title()}, {benchmarks.currency}):",
            f"  {benchmarks.start.isoformat()} → {benchmarks.end.isoformat()}",
        ]
        names = {
            "BTC": "BTC",
            "ETH": "ETH",
            "CASH": label("Cash (no interest)", "Efectivo (sin intereses)"),
            "BTC_ETH_50_50": label(
                "BTC/ETH 50/50 (buy and hold)", "BTC/ETH 50/50 (sin rebalanceo)"
            ),
        }
        for item in benchmarks.returns:
            value = (
                f"{item.return_pct:+.2f}%"
                if item.return_pct is not None
                else label(
                    "unavailable; missing or invalid closes",
                    "no disponible; faltan cierres válidos",
                )
            )
            lines.append(f"  {names[item.name]}: {value}")
        lines.append(
            label(
                "  Same hourly closes; no fees, slippage, interest or currency conversion. "
                "These references are not net account returns or a performance ranking.",
                "  Mismos cierres horarios; sin comisiones, deslizamiento, "
                "intereses ni conversión. "
                "Son referencias, no rentabilidad neta de la cuenta "
                "ni una clasificación de resultados.",
            )
        )
    lines.append(
        label(
            "Review details and proposals in WallyBot. "
            "Each real order requires your approval with MFA.",
            "Revisa el detalle y las propuestas en WallyBot. "
            "Cada orden real requiere tu aprobación con MFA.",
        )
    )
    if reconciliation is not None:
        severity = ReportSeverity.CRITICAL
    elif (
        inputs.active_breakers
        or stale_services
        or inputs.reconciliation_state in {"BLOCKED", "STALE"}
    ):
        severity = ReportSeverity.WARNING
    else:
        severity = ReportSeverity.INFO
    period = (
        ("diario" if inputs.period is ReportPeriod.DAILY else "semanal")
        if spanish
        else _PERIOD_LABEL[inputs.period]
    )
    title = (
        f"Informe {period}" if spanish else f"{period} report"
    ) + f" -- {inputs.now.date().isoformat()}"
    return ReportContent(severity=severity, title=title, body="\n".join(lines))
