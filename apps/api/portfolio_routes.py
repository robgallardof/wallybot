"""The signed-in user's read-only PAPER portfolio view."""

from typing import Literal, cast

from fastapi import APIRouter, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import PortfolioActivityView, PortfolioBalanceView, PortfolioView
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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
