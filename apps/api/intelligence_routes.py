from fastapi import APIRouter, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import (
    SmartMoneyRowView,
    SmartMoneyView,
    TokenRiskRowView,
    TokenRiskView,
    WhaleFlowView,
    WhaleTransferRowView,
)
from wallybot.infrastructure.smart_money_repository import SmartMoneyScoreRepository
from wallybot.infrastructure.token_risk_repository import TokenRiskScoreRepository
from wallybot.infrastructure.whale_flow_repository import WhaleTransferRepository

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


@router.get("/whale-flow", response_model=WhaleFlowView)
async def whale_flow(request: Request, user: SignedIn) -> WhaleFlowView:
    async with request.app.state.sessions() as db:
        signals = await WhaleTransferRepository(db).latest()
    return WhaleFlowView(
        rows=[
            WhaleTransferRowView(
                wallet_id=signal.wallet_id,
                chain=signal.chain,
                token=signal.token,
                action=signal.action.value,
                amount=str(signal.amount),
                value_usd=str(signal.value_usd),
                threshold_usd=str(signal.threshold_usd),
                occurred_at=signal.occurred_at.isoformat(),
                reasons=list(signal.reasons),
            )
            for signal in signals
        ]
    )


@router.get("/token-risk", response_model=TokenRiskView)
async def token_risk(request: Request, user: SignedIn) -> TokenRiskView:
    async with request.app.state.sessions() as db:
        scores = await TokenRiskScoreRepository(db).list_latest()
    return TokenRiskView(
        rows=[
            TokenRiskRowView(
                token_id=score.token_id,
                chain=score.chain,
                status=score.status.value,
                risk_score=str(score.risk_score) if score.risk_score is not None else None,
                computed_at=score.computed_at.isoformat(),
                reasons=list(score.reasons),
            )
            for score in scores
        ]
    )
