"""Explicit MFA-protected real-account configuration and read-only verified portfolio."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from apps.api.dependencies import Admin, SignedIn
from apps.api.schemas import Input
from wallybot.application.live_trading import LiveBlocked, account_id
from wallybot.domain.control import Environment
from wallybot.exchanges.private_errors import ExchangePrivateError
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.live_models import AnalystPortfolioRow, LiveControlRow
from wallybot.infrastructure.models import (
    ControlRow,
    FillRow,
    OrderIntentRow,
    ProviderConnectionRow,
)
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/live", tags=["real trading"])
# The live monitor holds the account lock for a few seconds every 30 s; saving limits waits it out.
LIMITS_LOCK_WAIT_SECONDS = 15


class LiveChange(Input):
    connection_id: str = Field(min_length=36, max_length=36)
    enabled: bool
    confirmation: Literal["LIVE"] | None = None
    max_order_usd: Decimal = Field(gt=0, le=100000)
    max_daily_loss_usd: Decimal = Field(gt=0, le=100000)
    max_total_usd: Decimal = Field(gt=0, le=1000000)
    slippage_pct: Decimal = Field(gt=0, le=Decimal("0.02"))

    @model_validator(mode="after")
    def explicit_activation(self):
        if self.enabled and self.confirmation != "LIVE":
            raise ValueError("Type LIVE to confirm real-money trading")
        if self.max_order_usd > self.max_total_usd:
            raise ValueError("Order limit must not exceed total exposure limit")
        return self


class LiveView(BaseModel):
    capable: bool = False
    configured: bool = False
    enabled: bool = False
    state: str = "NOT_CONFIGURED"
    reason: str = ""
    version: int | None = None
    connection_id: str | None = None
    venue: str | None = None
    cash_currency: str | None = None
    max_order_usd: str | None = None
    max_daily_loss_usd: str | None = None
    max_total_usd: str | None = None
    slippage_pct: str | None = None
    equity_usd: str | None = None
    as_of: str | None = None
    balances: list[dict[str, str]] = []
    orders: list[dict[str, str]] = []


async def view(request, user_id):
    service = request.app.state.live_trading
    config = await service.configuration(user_id)
    if config is None:
        return LiveView(capable=request.app.state.settings.live_capable)
    async with service.sessions() as db:
        connection = await db.get(ProviderConnectionRow, config.connection_id)
    venue = service.venue(connection.provider) if connection is not None else None
    async with service.sessions() as db:
        balances = await PortfolioRepository(db).list_balances(account_id(config))
        equity = await EquitySnapshotRepository(db).latest(account_id(config), "LIVE")
        orders = (
            await db.scalars(
                select(OrderIntentRow)
                .where(
                    OrderIntentRow.account_id == account_id(config),
                    OrderIntentRow.environment == "LIVE",
                )
                .order_by(OrderIntentRow.created_at.desc())
                .limit(50)
            )
        ).all()
        filled = (
            dict(
                (
                    await db.execute(
                        select(FillRow.client_order_id, func.sum(FillRow.quantity))
                        .where(
                            FillRow.account_id == account_id(config),
                            FillRow.environment == "LIVE",
                            FillRow.client_order_id.in_(
                                [order.client_order_id for order in orders]
                            ),
                        )
                        .group_by(FillRow.client_order_id)
                    )
                ).all()
            )
            if orders
            else {}
        )
    return LiveView(
        configured=True,
        capable=request.app.state.settings.live_capable,
        version=config.version,
        enabled=config.enabled,
        state=config.state,
        reason=config.reason,
        connection_id=config.connection_id,
        venue=venue.name if venue else None,
        cash_currency=venue.cash if venue else None,
        max_order_usd=str(config.max_order_usd),
        max_daily_loss_usd=str(config.max_daily_loss_usd),
        max_total_usd=str(config.max_total_usd),
        slippage_pct=str(config.slippage_pct),
        equity_usd=str(equity.equity) if equity else None,
        as_of=equity.recorded_at.isoformat() if equity else None,
        balances=[{"asset": b.currency, "amount": str(b.amount)} for b in balances],
        orders=[
            {
                "id": o.client_order_id,
                "pair": o.base + "/" + o.quote,
                "side": o.side,
                "quantity": str(o.quantity),
                "filled_quantity": str(filled.get(o.client_order_id, Decimal(0))),
                "limit_price": str(o.limit_price),
                "status": o.status,
                "created_at": o.created_at.isoformat(),
            }
            for o in orders
        ],
    )


@router.get("", response_model=LiveView)
async def get_live(request: Request, user: SignedIn):
    try:
        return await view(request, user.id)
    except LiveBlocked as exc:
        raise HTTPException(404, str(exc)) from None


class LivePosition(BaseModel):
    asset: str
    quantity: str
    price: str | None = None
    value: str | None = None
    average_price: str | None = None
    held_since: str | None = None
    pnl: str | None = None
    pnl_pct: str | None = None
    source: str | None = None


class LivePositionsView(BaseModel):
    cash_currency: str | None = None
    as_of: str | None = None
    positions: list[LivePosition] = []


class PricePoint(BaseModel):
    t: str
    close: str


class PriceHistoryView(BaseModel):
    asset: str
    timeframe: str
    average_price: str | None = None
    held_since: str | None = None
    points: list[PricePoint] = []


@router.get("/positions", response_model=LivePositionsView)
async def live_positions(request: Request, user: SignedIn):
    """Per-coin entry, current value and result from the last verified real-account sync."""
    async with request.app.state.live_trading.sessions() as db:
        context = await db.get(AnalystPortfolioRow, user.id)
    if context is None:
        return LivePositionsView()
    cash = "USDT" if context.venue == "binance" else "USD"
    rows = []
    for asset, amount in sorted((context.holdings or {}).items()):
        facts = (context.positions or {}).get(asset, {})
        quantity = Decimal(amount)
        price = Decimal(facts["price"]) if facts.get("price") else None
        entry = Decimal(facts["average_price"]) if facts.get("average_price") else None
        row = LivePosition(
            asset=asset,
            quantity=amount,
            price=str(price) if price is not None else None,
            value=str(quantity * price) if price is not None else None,
            average_price=str(entry) if entry is not None else None,
            held_since=facts.get("held_since"),
            source=facts.get("source"),
        )
        if price is not None and entry:
            row.pnl = str((price - entry) * quantity)
            row.pnl_pct = str((price / entry - 1) * 100)
        rows.append(row)
    rows.sort(key=lambda row: Decimal(row.value or 0), reverse=True)
    return LivePositionsView(cash_currency=cash, as_of=context.as_of.isoformat(), positions=rows)


@router.get("/positions/{asset}/history", response_model=PriceHistoryView)
async def live_position_history(asset: str, request: Request, user: SignedIn):
    """Closing prices since the coin was bought (30 days when the entry is unknown)."""
    service = request.app.state.live_trading
    config = await service.configuration(user.id)
    async with service.sessions() as db:
        context = await db.get(AnalystPortfolioRow, user.id)
        connection = await db.get(ProviderConnectionRow, config.connection_id) if config else None
    if context is None or connection is None or asset not in (context.holdings or {}):
        raise HTTPException(404, "This coin is not held in the real account")
    venue = service.venue(connection.provider)
    facts = (context.positions or {}).get(asset, {})
    now = datetime.now(UTC)
    since = (
        datetime.fromisoformat(facts["held_since"])
        if facts.get("held_since")
        else now - timedelta(days=30)
    )
    # Pad the start so the entry is visible, then pick the finest interval that fits.
    since = min(since, now - timedelta(days=1))
    since -= (now - since) * 0.05
    span = now - since
    timeframe = "5m" if span <= timedelta(days=3) else "1h" if span <= timedelta(days=40) else "1d"
    instrument = next(
        (
            i
            for i in await venue.market.discover_instruments()
            if i.base == asset and i.quote == venue.cash
        ),
        None,
    )
    if instrument is None:
        raise HTTPException(404, "This coin has no price history on the exchange")
    candles = await venue.market.fetch_candles(instrument, timeframe, since, 1000)
    return PriceHistoryView(
        asset=asset,
        timeframe=timeframe,
        average_price=facts.get("average_price"),
        held_since=facts.get("held_since"),
        points=[PricePoint(t=c.close_time.isoformat(), close=str(c.close)) for c in candles],
    )


async def _keep_enabled(service, was_enabled):
    if not was_enabled:
        return
    async with service.sessions.begin() as db:
        stored = await db.get(LiveControlRow, 1, with_for_update=True)
        stored.enabled = True
        control = await db.get(ControlRow, 1, with_for_update=True)
        control.environment = Environment.LIVE


@router.post("/control", response_model=LiveView)
async def configure_live(body: LiveChange, request: Request, user: Admin):
    if body.enabled and not request.app.state.settings.live_capable:
        raise HTTPException(409, "This deployment has real trading capability disabled")
    service = request.app.state.live_trading
    try:
        async with service.serialized(wait_seconds=LIMITS_LOCK_WAIT_SECONDS):
            existing = await service.configuration(user.id)
            async with service.sessions() as db:
                connection = await db.get(ProviderConnectionRow, body.connection_id)
            if (
                connection is None
                or connection.user_id != user.id
                or connection.provider not in {"KRAKEN", "BINANCE"}
                or connection.mode != "TRADE_ONLY"
            ):
                raise LiveBlocked("Select your own verified spot trading connection")
            # A failed re-activation must not switch off an account that was already live: it
            # stays enabled but BLOCKED, so the monitor re-arms it once the cause is gone.
            was_enabled = existing is not None and existing.enabled
            if existing is not None and existing.connection_id != body.connection_id:
                raise LiveBlocked(
                    "Changing the initialized real account requires separate reconciliation"
                )
            async with service.sessions.begin() as db:
                config = await db.get(LiveControlRow, 1, with_for_update=True)
                if config is None:
                    config = LiveControlRow(
                        id=1,
                        owner_id=user.id,
                        connection_id=body.connection_id,
                        enabled=False,
                        initialized=False,
                        version=0,
                    )
                    db.add(config)
                config.enabled = False
                config.state, config.reason = "DISABLED", ""
                config.max_order_usd = body.max_order_usd
                config.max_daily_loss_usd = body.max_daily_loss_usd
                config.max_total_usd = body.max_total_usd
                config.slippage_pct = body.slippage_pct
                config.version += 1
                control = await db.get(ControlRow, 1, with_for_update=True)
                if control.environment == Environment.LIVE:
                    control.environment = Environment.OBSERVE
                audit(db, "LIVE_LIMITS_CONFIGURED", user.id)
            if body.enabled:
                try:
                    await service._sync(config, initialize=True)
                except (LiveBlocked, ExchangePrivateError) as exc:
                    await service.latch(str(exc))
                    await _keep_enabled(service, was_enabled)
                    raise LiveBlocked(str(exc)) from None
                except Exception:
                    await service.latch("Cannot verify the real account; no new trades are allowed")
                    await _keep_enabled(service, was_enabled)
                    raise LiveBlocked(
                        "Cannot verify real permissions, balances, prices and reconciliation"
                    ) from None
                async with service.sessions.begin() as db:
                    stored = await db.get(LiveControlRow, 1, with_for_update=True)
                    stored.enabled, stored.state, stored.reason = True, "READY", ""
                    control = await db.get(ControlRow, 1, with_for_update=True)
                    control.environment = Environment.LIVE
                    audit(db, "LIVE_ACTIVATED", user.id)
            else:
                async with service.sessions.begin() as db:
                    audit(db, "LIVE_DISABLED", user.id)
    except LiveBlocked as exc:
        raise HTTPException(409, str(exc)) from None
    return await view(request, user.id)
