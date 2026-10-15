"""Shared, read-only proposal cards for Telegram commands and scheduled alerts.

Ranking compares stated price scenarios, never an estimated probability or promised return.
The risk label is an explicit presentation heuristic, not a replacement for RiskEngine.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.live_models import AnalystPortfolioRow, LiveControlRow
from wallybot.infrastructure.models import ControlRow, TradeProposalRow
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.notifications.telegram_i18n import Language

HUNDRED = Decimal(100)


@dataclass(frozen=True)
class ProposalDisplayContext:
    environment: str = "OBSERVE"
    live_version: int | None = None
    venue: str | None = None
    quote: str | None = None
    equity: Decimal | None = None
    cash: Decimal | None = None
    max_order: Decimal | None = None
    as_of: datetime | None = None

    @property
    def binding(self) -> str:
        return f"{self.environment}:{self.live_version or 0}"


async def display_context(db: AsyncSession, owner_id: str, now: datetime) -> ProposalDisplayContext:
    control = await db.get(ControlRow, 1)
    environment = control.environment if control else "OBSERVE"
    if environment != "LIVE":
        return ProposalDisplayContext(environment=environment)
    live = await db.get(LiveControlRow, 1)
    if live is None or live.owner_id != owner_id:
        return ProposalDisplayContext(environment=environment)
    context = ProposalDisplayContext(environment=environment, live_version=live.version)
    portfolio = await db.get(AnalystPortfolioRow, owner_id)
    equity = await EquitySnapshotRepository(db).latest("live:" + live.connection_id, "LIVE")
    if (
        not live.enabled
        or live.state != "READY"
        or portfolio is None
        or equity is None
        or not timedelta(0) <= now - portfolio.as_of <= timedelta(seconds=60)
        or not timedelta(0) <= now - equity.recorded_at <= timedelta(seconds=60)
    ):
        return context
    quote = {"binance": "USDT", "kraken": "USD"}.get(portfolio.venue)
    return ProposalDisplayContext(
        environment=environment,
        live_version=live.version,
        venue=portfolio.venue,
        quote=quote,
        equity=equity.equity,
        cash=portfolio.cash_usd,
        max_order=live.max_order_usd,
        as_of=min(portfolio.as_of, equity.recorded_at),
    )


def price_scenarios(row: TradeProposalRow) -> tuple[Decimal | None, Decimal | None]:
    if row.entry_price <= 0 or row.direction != "LONG":
        return None, None
    gain = (row.take_profit_price / row.entry_price - 1) if row.take_profit_price else None
    loss = (1 - row.stop_price / row.entry_price) if row.stop_price else None
    return gain if gain is not None and gain > 0 else None, (
        loss if loss is not None and loss > 0 else None
    )


def risk_label(row: TradeProposalRow) -> str:
    _, loss = price_scenarios(row)
    if loss is None:
        return "HIGH"
    if loss <= Decimal("0.02") and row.suggested_allocation_pct <= Decimal("0.05"):
        return "LOW"
    if loss <= Decimal("0.05") and row.suggested_allocation_pct <= Decimal("0.10"):
        return "MEDIUM"
    return "HIGH"


def rank_proposals(rows: list[TradeProposalRow], now: datetime) -> list[TradeProposalRow]:
    def key(row: TradeProposalRow):
        gain, loss = price_scenarios(row)
        active = row.decision_status == "PENDING" and expires_at(row) > now
        comparable = gain is not None and loss is not None
        ratio = gain / loss if comparable and gain is not None and loss is not None else Decimal(0)
        return (
            active,
            comparable,
            ratio,
            gain or Decimal(0),
            row.confidence,
            row.as_of,
            row.proposal_id,
        )

    return sorted(rows, key=key, reverse=True)


def expires_at(row: TradeProposalRow) -> datetime:
    return row.as_of + timedelta(seconds=float(row.signal_ttl_seconds))


def _evidence(values: list, missing: str) -> str:
    # Keep every card below Telegram's limit, including untrusted analyst text.
    items = [" ".join(str(value).split()) for value in values[:3]]
    summary = "; ".join(item if len(item) <= 180 else item[:179] + "…" for item in items)
    if len(values) > 3:
        summary += f" (+{len(values) - 3})"
    return summary or missing


def proposal_notification(
    row: TradeProposalRow,
    position: int,
    context: ProposalDisplayContext,
    now: datetime,
    language: Language = "es",
    web_origin: str | None = None,
) -> Notification:
    en = language == "en"
    gain, loss = price_scenarios(row)
    missing = "Unavailable" if en else "No disponible"

    def pct(value: Decimal | None) -> str:
        return f"{value * HUNDRED:.2f}%" if value is not None else missing

    expiry = expires_at(row)
    active = row.decision_status == "PENDING" and expiry > now
    status = (
        row.decision_status
        if row.decision_status != "PENDING" or active
        else ("EXPIRED" if en else "CADUCADA")
    )
    action = (
        ("BUY" if en else "COMPRAR")
        if row.direction == "LONG"
        else ("REDUCE / SELL" if en else "REDUCIR / VENDER")
    )
    lines = [
        f"{action} {row.base}/{row.quote} · {row.venue} · {context.environment}",
        f"{'Status' if en else 'Estado'}: {status}",
        f"{'Risk' if en else 'Riesgo'}: {risk_label(row)} · "
        + (
            "stop distance + allocation heuristic; not a safety rating"
            if en
            else "orientativo por stop y asignación; LOW no significa inversión segura"
        ),
        f"{'Entry' if en else 'Entrada de referencia'}: {row.entry_price} {row.quote}",
        f"{'Allocation suggested by analysts' if en else 'Asignación sugerida por analistas'}: "
        f"{pct(row.suggested_allocation_pct)} "
        f"{'of portfolio value' if en else 'del valor de cartera'}",
    ]
    amount = None
    if (
        context.equity is not None
        and context.cash is not None
        and context.venue == row.venue
        and context.quote == row.quote
        and context.equity.is_finite()
        and context.cash.is_finite()
        and context.equity > 0
        and context.cash >= 0
        and row.direction == "LONG"
    ):
        target = context.equity * row.suggested_allocation_pct
        desired = min(target, context.max_order or target)
        amount = min(desired, context.cash)
        lines.append(
            f"Indicative amount: {amount:.2f} {row.quote}; allocation target {target:.2f}; "
            f"observed cash {context.cash:.2f}."
            if en
            else f"Importe orientativo: {amount:.2f} {row.quote}; "
            f"objetivo de asignación {target:.2f}; "
            f"efectivo observado {context.cash:.2f}."
        )
        lines.append(
            ("Balances at " if en else "Saldos al ") + f"{context.as_of:%Y-%m-%d %H:%M:%S} UTC"
        )
        lines.append(
            "Before fees and other limits; final amount is revalidated."
            if en
            else "Antes de comisiones y otros límites; el importe final se revalida."
        )
        if desired > context.cash:
            shortfall = desired - context.cash
            lines.append(
                f"Cash shortfall for that capped allocation: {shortfall:.2f} {row.quote} "
                "before fees; you can use the smaller amount."
                if en
                else f"Para cubrir esa asignación con el tope por orden faltan {shortfall:.2f} "
                f"{row.quote} antes de costes; puedes usar el importe menor."
            )

    else:
        lines.append(
            "Amount unavailable: no fresh verified account valuation in this currency."
            if en
            else "Importe no disponible: falta valoración vigente de tu cuenta en esta moneda."
        )
    lines += [
        f"{'Why' if en else 'Por qué'}: {_evidence(row.reasons, missing)}",
        f"{'Risks' if en else 'Riesgos concretos'}: {_evidence(row.risks, missing)}",
        f"{'Invalidated if' if en else 'Se invalida si'}: "
        f"{_evidence(row.invalidating_conditions, missing)}",
        f"Stop: {row.stop_price or missing} {row.quote} · "
        f"{'loss to stop' if en else 'caída hasta stop'}: {pct(loss)}",
        f"{'Target' if en else 'Objetivo'}: {row.take_profit_price or missing} {row.quote} · "
        f"{'gross potential to target' if en else 'potencial bruto hasta objetivo'}: {pct(gain)}",
    ]
    if gain is not None and loss is not None:
        lines.append(f"{'Reward/risk' if en else 'Beneficio/riesgo'}: {gain / loss:.2f}:1")
        if amount is not None:
            lines.append(
                f"Gross scenario: +{amount * gain:.2f} / -{amount * loss:.2f} {row.quote}."
                if en
                else f"Escenario bruto: +{amount * gain:.2f} / -{amount * loss:.2f} {row.quote}."
            )
    lines += [
        f"{'Planned horizon' if en else 'Horizonte previsto'}: "
        f"{row.time_horizon_seconds / Decimal(3600):.2f} {'hours' if en else 'horas'}",
        f"{'Analysis' if en else 'Análisis'}: {row.as_of.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC",
        f"{'Approve before' if en else 'Aprobar antes de'}: "
        f"{expiry.astimezone(UTC):%Y-%m-%d %H:%M:%S} UTC",
        (
            "Ranked by reward/risk, then gross target potential; "
            "not an expected or guaranteed return."
            if en
            else "Orden: beneficio/riesgo y después potencial bruto. "
            "No es rendimiento esperado ni garantizado."
        ),
        (
            "Stop and target are reference levels, not automatic exit orders."
            if en
            else "Stop y objetivo son referencias; no son órdenes de salida automáticas."
        ),
        f"ID: {row.proposal_id}",
    ]
    if row.execution_status:
        lines.append(f"{row.execution_environment or 'PAPER'} {row.execution_status}")
        lines.append(_evidence(row.execution_reasons or [], missing))
    if web_origin:
        query = urlencode({"proposal": row.proposal_id})
        lines.append(f"{web_origin.rstrip('/')}/intelligence?{query}#proposals")
    markup = None
    if active:
        lines.append(f"/approve {row.proposal_id} · /reject {row.proposal_id}")
        buttons = []
        for decision, label in (
            ("approve", "Approve" if en else "Aprobar"),
            ("reject", "Reject" if en else "Rechazar"),
        ):
            data = f"{decision}:{row.proposal_id}:{context.binding}"
            if len(data.encode()) <= 64:
                buttons.append({"text": f"{label} · {context.environment}", "callback_data": data})
        if buttons:
            markup = {"inline_keyboard": [buttons]}
    return Notification(
        NotificationSeverity.INFO, f"#{position} · {row.base}/{row.quote}", "\n".join(lines), markup
    )
