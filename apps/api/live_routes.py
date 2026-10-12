"""Explicit MFA-protected real-account configuration and read-only verified portfolio."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from apps.api.dependencies import Admin, SignedIn
from apps.api.schemas import Input
from wallybot.application.live_trading import LiveBlocked, account_id
from wallybot.domain.control import Environment
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.live_models import LiveControlRow
from wallybot.infrastructure.models import (
    ControlRow,
    FillRow,
    OrderIntentRow,
    ProviderConnectionRow,
)
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/live", tags=["real trading"])


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


@router.post("/control", response_model=LiveView)
async def configure_live(body: LiveChange, request: Request, user: Admin):
    if body.enabled and not request.app.state.settings.live_capable:
        raise HTTPException(409, "This deployment has real trading capability disabled")
    service = request.app.state.live_trading
    try:
        async with service.serialized():
            existing = await service.configuration(user.id)
            async with service.sessions() as db:
                connection = await db.get(ProviderConnectionRow, body.connection_id)
            if (
                connection is None
                or connection.user_id != user.id
                or connection.provider != "KRAKEN"
                or connection.mode != "TRADE_ONLY"
            ):
                raise LiveBlocked("Select your own verified Kraken trading connection")
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
                except LiveBlocked as exc:
                    await service.latch(str(exc))
                    raise
                except Exception:
                    await service.latch("Cannot verify the real account; no new trades are allowed")
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
