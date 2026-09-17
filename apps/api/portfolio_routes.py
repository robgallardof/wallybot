"""The signed-in user's read-only PAPER portfolio view, plus one-time initial PAPER funding."""

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import OrderCancelView, PortfolioActivityView, PortfolioBalanceView, PortfolioView
from apps.api.schemas import PortfolioFund
from wallybot.application.ledger_postings import build_initial_funding_transaction
from wallybot.infrastructure.models import OrderIntentRow
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository
from wallybot.infrastructure.unit_of_work import unit_of_work

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# The only cash currency this pipeline trades against, same assumption
# `wallybot.application.equity_tracker` and every existing strategy/pair already make.
CASH_CURRENCY = "USD"


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
        fills = await repository.list_recent_fills(account_id)
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
        ],
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
