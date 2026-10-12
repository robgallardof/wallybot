"""The signed-in user's read-only PAPER portfolio view, plus one-time initial PAPER funding."""

import csv
import io
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import (
    OrderCancelView,
    PortfolioActivityView,
    PortfolioBalanceView,
    PortfolioOrderView,
    PortfolioPerformanceView,
    PortfolioProposalHistoryView,
    PortfolioView,
)
from apps.api.schemas import PortfolioFund
from wallybot.application.ledger_postings import build_initial_funding_transaction
from wallybot.application.paper_accounts import paper_ai_account_id
from wallybot.application.portfolio_performance import compute_fifo_performance
from wallybot.application.position_monitoring import (
    attribute_fifo_positions,
    fetch_position_marks,
    level_status,
    trustworthy_mark,
)
from wallybot.domain.market import Instrument, MarketType
from wallybot.infrastructure.models import OrderIntentRow, TradeProposalRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository
from wallybot.infrastructure.unit_of_work import unit_of_work
from wallybot.security.auth import Identity

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
    return await _build_portfolio_view(request, user, paper_account_id(user.id))


@router.get("/ai", response_model=PortfolioView)
async def get_ai_portfolio(request: Request, user: SignedIn) -> PortfolioView:
    """Same shape as `GET /api/portfolio`, but for the fully separate AI-autonomous account
    (`paper-ai:<user_id>`) -- see `docs/adr/016-ai-autonomous-account.md` (2026-09-23) for why
    this is a distinct ledger namespace rather than a filter on the same one."""
    return await _build_portfolio_view(request, user, paper_ai_account_id(user.id))


async def _build_portfolio_view(request: Request, user: Identity, account_id: str) -> PortfolioView:
    async with request.app.state.sessions() as db:
        repository = PortfolioRepository(db)
        balances = await repository.list_balances(account_id)
        fills = await repository.list_recent_fills(account_id, limit=EXPORT_FILL_LIMIT + 1)
        if len(fills) > EXPORT_FILL_LIMIT:
            raise HTTPException(
                status_code=503, detail="Portfolio history exceeds the display limit"
            )
        connections = await ProviderConnectionRepository(db).list_for_user(user.id)
        orders = (
            (
                await db.execute(
                    select(OrderIntentRow)
                    .where(
                        OrderIntentRow.account_id == account_id,
                        OrderIntentRow.environment == "PAPER",
                    )
                    .order_by(OrderIntentRow.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )
        proposals_by_order_id = {
            row.execution_order_id: row
            for row in (
                await db.scalars(
                    select(TradeProposalRow).where(
                        TradeProposalRow.owner_id == user.id,
                        TradeProposalRow.execution_order_id.in_(
                            [fill.client_order_id for fill in fills]
                        ),
                    )
                )
            )
            if row.execution_order_id is not None
        }

    positions = attribute_fifo_positions(reversed(fills))
    linked_fills = [fill for fill in fills[:50] if fill.client_order_id in proposals_by_order_id]
    marks = await fetch_position_marks(
        getattr(request.app.state, "portfolio_market_provider", None),
        [fill for fill in linked_fills if positions[fill.fill_id].remaining_quantity > 0],
    )
    now = datetime.now(UTC)
    history = []
    for fill in linked_fills:
        proposal = proposals_by_order_id[fill.client_order_id]
        position = positions[fill.fill_id]
        instrument = Instrument(fill.venue, MarketType.SPOT, fill.base, fill.quote)
        mark = marks.get((fill.venue, fill.base, fill.quote))
        if mark is not None and not trustworthy_mark(mark, instrument, now):
            mark = None
        price = mark.bid if mark is not None else None
        end = position.closed_at or now
        history.append(
            PortfolioProposalHistoryView(
                proposal_id=proposal.proposal_id,
                base=fill.base,
                quote=fill.quote,
                direction="BUY" if fill.side == "BUY" else "SELL",
                filled_quantity=str(fill.quantity),
                filled_price=str(fill.price),
                filled_at=fill.filled_at.isoformat(),
                held_for_seconds=max(0, int((end - fill.filled_at).total_seconds())),
                stop_price=str(proposal.stop_price) if proposal.stop_price is not None else None,
                take_profit_price=(
                    str(proposal.take_profit_price)
                    if proposal.take_profit_price is not None
                    else None
                ),
                execution_status=proposal.execution_status or "UNKNOWN",
                remaining_quantity=str(position.remaining_quantity),
                realized_pnl=str(position.realized_pnl),
                current_price=str(price) if price is not None else None,
                quote_at=mark.timestamp.isoformat() if mark is not None else None,
                quote_source=mark.source if mark is not None else None,
                unrealized_pnl=(
                    "0"
                    if position.remaining_quantity == 0
                    else str(position.remaining_quantity * price - position.remaining_cost)
                    if price is not None
                    else None
                ),
                closed_at=position.closed_at.isoformat()
                if position.closed_at is not None
                else None,
                monitoring_status="REDUCTION_FILLED"
                if fill.side == "SELL"
                else level_status(
                    position.remaining_quantity,
                    price,
                    proposal.stop_price,
                    proposal.take_profit_price,
                ),
            )
        )

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
                proposal_id=(
                    proposals_by_order_id[fill.client_order_id].proposal_id
                    if fill.client_order_id in proposals_by_order_id
                    else None
                ),
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
        proposal_history=history,
        orders=[
            PortfolioOrderView(
                client_order_id=row.client_order_id,
                venue=row.venue,
                base=row.base,
                quote=row.quote,
                side=cast(Literal["BUY", "SELL"], row.side),
                kind=cast(Literal["MARKET", "LIMIT"], row.kind),
                quantity=str(row.quantity),
                limit_price=str(row.limit_price) if row.limit_price is not None else None,
                status=row.status,
                created_at=row.created_at.isoformat(),
                expires_at=row.expires_at.isoformat(),
            )
            for row in orders
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


@router.post("/ai/fund", response_model=PortfolioView, status_code=201)
async def fund_ai_portfolio(body: PortfolioFund, request: Request, user: Admin) -> PortfolioView:
    """Same one-time-funding pattern as `POST /api/portfolio/fund`, for the fully separate
    AI-autonomous account (`paper-ai:<user_id>`) instead of the deterministic one."""
    account_id = paper_ai_account_id(user.id)
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

    return await get_ai_portfolio(request, user)


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
