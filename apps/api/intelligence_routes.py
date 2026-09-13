from fastapi import APIRouter, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import SmartMoneyRowView, SmartMoneyView
from wallybot.infrastructure.smart_money_repository import SmartMoneyScoreRepository

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("/smart-money", response_model=SmartMoneyView)
async def smart_money(request: Request, user: SignedIn) -> SmartMoneyView:
    async with request.app.state.sessions() as db:
        snapshots = await SmartMoneyScoreRepository(db).list_latest()
    return SmartMoneyView(
        rows=[
            SmartMoneyRowView(
                wallet_id=snapshot.wallet_id,
                status=snapshot.status.value,
                score=str(snapshot.score) if snapshot.score is not None else None,
                trade_count=snapshot.trade_count,
                win_rate=str(snapshot.win_rate) if snapshot.win_rate is not None else None,
                realized_pnl_usd=(
                    str(snapshot.realized_pnl_usd)
                    if snapshot.realized_pnl_usd is not None
                    else None
                ),
                computed_at=snapshot.computed_at.isoformat(),
                reasons=list(snapshot.reasons),
            )
            for snapshot in snapshots
        ]
    )
