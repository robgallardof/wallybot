"""The signed-in user's read-only PAPER portfolio view, plus one-time initial PAPER funding."""

import csv
import io
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import (
    OrderCancelView,
    PortfolioActivityView,
    PortfolioBalanceView,
    PortfolioPerformanceView,
    PortfolioView,
)
from apps.api.schemas import PortfolioFund
from wallybot.application.ledger_postings import build_initial_funding_transaction
from wallybot.application.portfolio_performance import compute_fifo_performance
from wallybot.infrastructure.models import OrderIntentRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository
from wallybot.infrastructure.unit_of_work import unit_of_work

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# The only cash currency this pipeline trades against, same assumption
# `wallybot.application.equity_tracker` and every existing strategy/pair already make.
CASH_CURRENCY = "USD"

# A safety cap on a full-history export, not a business limit -- large enough that no real PAPER
# account (this system's own trading cadence) could plausibly exceed it, small enough to bound
# memory for one request.
EXPORT_FILL_LIMIT = 50_000
_EXPORT_FIELDNAMES: tuple[str, ...] = (
    "id",
    "venue",
    "base",
    "quote",
    "side",
    "quantity",
    "price",
    "fee",
    "fee_currency",
    "occurred_at",
)


def paper_account_id(user_id: str) -> str:
    """Return the only ledger namespace the web API may expose for a user.

    PAPER writers use this stable, bounded identifier.  It prevents an authenticated user from
    selecting an arbitrary account id and inspecting another tenant's ledger.
    """
    return f"paper:{user_id}"


@router.get("", response_model=PortfolioView)
async def get_portfolio(request: Request, user: SignedIn) -> PortfolioView:
    account_id = paper_account_id(user.id)
    async with request.app.state.sessions() as db:
        repository = PortfolioRepository(db)
        balances = await repository.list_balances(account_id)
        fills = await repository.list_recent_fills(account_id, limit=EXPORT_FILL_LIMIT)
        connections = await ProviderConnectionRepository(db).list_for_user(user.id)

    return PortfolioView(
        environment="PAPER",
        connection_count=len(connections),
        balances=[
            PortfolioBalanceView(
                currency=balance.currency,
                # ledger_postings.py only ever writes CASH/POSITION under a user's own
                # account_id -- CLEARING/FEE legs live under the fixed "clearing" account_id.
                purpose=cast(Literal["CASH", "POSITION"], balance.purpose),
                amount=str(balance.amount),
            )
            for balance in balances
        ],
        activity=[
            PortfolioActivityView(
                id=fill.fill_id,
                venue=fill.venue,
                base=fill.base,
                quote=fill.quote,
                side=cast(Literal["BUY", "SELL"], fill.side),
                quantity=str(fill.quantity),
                price=str(fill.price),
                fee=str(fill.fee),
                fee_currency=fill.fee_currency,
                occurred_at=fill.filled_at.isoformat(),
            )
            for fill in fills
        ][:50],
        performance=[
            PortfolioPerformanceView(
                quote=item.quote,
                realized_pnl=str(item.realized_pnl),
                open_cost_basis=str(item.open_cost_basis),
            )
            for item in compute_fifo_performance(reversed(fills))
        ],
    )


@router.get("/export")
async def export_portfolio_activity(
    request: Request, user: SignedIn, format: Literal["csv", "json"] = "csv"
) -> Response:
    """Export the signed-in user's own fill history as CSV or JSON.

    Same raw ledger fields `get_portfolio`'s `activity` exposes (id, venue, instrument, side,
    quantity, price, fee, fee_currency, occurred_at).  Aggregate realised PnL and open cost basis
    are deliberately presented separately in the portfolio summary, where FIFO matching can be
    applied across the complete history.  A per-row PnL column would be ambiguous for a partial
    FIFO close and must not be fabricated.
    """
    account_id = paper_account_id(user.id)
    async with request.app.state.sessions() as db:
        fills = await PortfolioRepository(db).list_recent_fills(account_id, limit=EXPORT_FILL_LIMIT)

    rows = [
        {
            "id": fill.fill_id,
            "venue": fill.venue,
            "base": fill.base,
            "quote": fill.quote,
            "side": fill.side,
            "quantity": str(fill.quantity),
            "price": str(fill.price),
            "fee": str(fill.fee),
            "fee_currency": fill.fee_currency,
            "occurred_at": fill.filled_at.isoformat(),
        }
        for fill in fills
    ]

    if format == "json":
        return JSONResponse(
            rows,
            headers={"Content-Disposition": 'attachment; filename="wallybot-operaciones.json"'},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_EXPORT_FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="wallybot-operaciones.csv"'},
    )


@router.post("/fund", response_model=PortfolioView, status_code=201)
async def fund_portfolio(body: PortfolioFund, request: Request, user: Admin) -> PortfolioView:
    """Seed the signed-in admin's PAPER account with an explicit starting cash balance.

    One-time per account: `build_initial_funding_transaction` gives the transaction a fixed
    `reference_id`, so the table's own unique constraint -- not a racy check-then-act read --
    rejects a second attempt. There is no separate withdrawal/adjustment route; correcting a
    mistaken amount means starting a fresh PAPER account, the same manual-reset posture the rest
    of this codebase uses for PAPER state.
    """
    account_id = paper_account_id(user.id)
    now = datetime.now(UTC)
    transaction = build_initial_funding_transaction(
        account_id=account_id,
        currency=CASH_CURRENCY,
        amount=body.amount,
        transaction_id=str(uuid4()),
        now=now,
    )
    try:
        async with unit_of_work(request.app.state.sessions) as uow:
            await uow.save_ledger_transaction(transaction)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="This account is already funded") from exc

    return await get_portfolio(request, user)


@router.post("/orders/{client_order_id}/cancel", response_model=OrderCancelView)
async def cancel_order(client_order_id: str, request: Request, user: Admin) -> OrderCancelView:
    """Request cancellation of one of the signed-in admin's own still-open PAPER orders.

    RISK.md lists "CANCEL OPEN ORDERS" as a control action distinct from pausing new entries --
    "does not close filled positions." `ExecutionService.cancel` is the authoritative resolver
    (durable CANCEL_REQUESTED claim, then a real gateway lookup); this route only resolves
    ownership and rejects a client_order_id that does not belong to the caller's own account,
    the same isolation `get_portfolio` already enforces for reads.
    """
    account_id = paper_account_id(user.id)
    async with request.app.state.sessions() as db:
        row = await db.get(OrderIntentRow, client_order_id)
    if row is None or row.account_id != account_id:
        raise HTTPException(status_code=404, detail="Order not found")

    status = await request.app.state.execution.cancel(
        client_order_id, row.venue, row.account_id, row.environment
    )
    return OrderCancelView(client_order_id=client_order_id, status=status)
