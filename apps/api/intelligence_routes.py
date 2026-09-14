from fastapi import APIRouter, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import (
    EntityGraphView,
    PriceConsensusRowView,
    PriceConsensusView,
    ProviderReliabilityRowView,
    ProviderReliabilityView,
    RelationshipRowView,
    SmartMoneyRowView,
    SmartMoneyView,
    TokenRiskRowView,
    TokenRiskView,
    WalletActivityRowView,
    WalletActivityView,
    WhaleFlowView,
    WhaleTransferRowView,
)
from wallybot.infrastructure.price_consensus_repository import PriceConsensusRepository
from wallybot.infrastructure.provider_reliability_repository import (
    ProviderReliabilityRepository,
)
from wallybot.infrastructure.relationship_repository import RelationshipRepository
from wallybot.infrastructure.smart_money_repository import SmartMoneyScoreRepository
from wallybot.infrastructure.token_risk_repository import TokenRiskScoreRepository
from wallybot.infrastructure.wallet_activity_repository import WalletActivityRepository
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


@router.get("/provider-reliability", response_model=ProviderReliabilityView)
async def provider_reliability(request: Request, user: SignedIn) -> ProviderReliabilityView:
    async with request.app.state.sessions() as db:
        snapshots = await ProviderReliabilityRepository(db).list_latest()
    return ProviderReliabilityView(
        rows=[
            ProviderReliabilityRowView(
                provider=snapshot.provider,
                status=snapshot.status.value,
                call_count=snapshot.call_count,
                error_rate=str(snapshot.error_rate) if snapshot.error_rate is not None else None,
                average_latency_ms=(
                    str(snapshot.average_latency_ms)
                    if snapshot.average_latency_ms is not None
                    else None
                ),
                seconds_since_last_success=(
                    str(snapshot.seconds_since_last_success)
                    if snapshot.seconds_since_last_success is not None
                    else None
                ),
                computed_at=snapshot.computed_at.isoformat(),
                reasons=list(snapshot.reasons),
            )
            for snapshot in snapshots
        ]
    )


@router.get("/price-consensus", response_model=PriceConsensusView)
async def price_consensus(request: Request, user: SignedIn) -> PriceConsensusView:
    async with request.app.state.sessions() as db:
        results = await PriceConsensusRepository(db).list_latest()
    return PriceConsensusView(
        rows=[
            PriceConsensusRowView(
                instrument_id=result.instrument_id,
                status=result.status.value,
                consensus_price=(
                    str(result.consensus_price) if result.consensus_price is not None else None
                ),
                included_sources=list(result.included_sources),
                excluded_sources=list(result.excluded_sources),
                computed_at=result.computed_at.isoformat(),
                reasons=list(result.reasons),
            )
            for result in results
        ]
    )


@router.get("/wallet-activity", response_model=WalletActivityView)
async def wallet_activity(request: Request, user: SignedIn) -> WalletActivityView:
    async with request.app.state.sessions() as db:
        events = await WalletActivityRepository(db).list_recent()
    return WalletActivityView(
        rows=[
            WalletActivityRowView(
                wallet_id=event.wallet_id,
                chain=event.chain,
                token=event.token,
                action=event.action.value,
                amount=str(event.amount),
                value_usd=str(event.value_usd) if event.value_usd is not None else None,
                price=str(event.price) if event.price is not None else None,
                occurred_at=event.occurred_at.isoformat(),
                attribution_source=event.attribution.source,
                attribution_confidence=str(event.attribution.confidence),
            )
            for event in events
        ]
    )


@router.get("/entity-graph", response_model=EntityGraphView)
async def entity_graph(request: Request, user: SignedIn) -> EntityGraphView:
    async with request.app.state.sessions() as db:
        relationships = await RelationshipRepository(db).list_recent()
    return EntityGraphView(
        rows=[
            RelationshipRowView(
                id=relationship.id,
                source_type=relationship.source.node_type.value,
                source_id=relationship.source.node_id,
                relationship_type=relationship.relationship_type.value,
                target_type=relationship.target.node_type.value,
                target_id=relationship.target.node_id,
                attribution_source=relationship.attribution.source,
                attribution_confidence=str(relationship.attribution.confidence),
                created_at=relationship.created_at.isoformat(),
            )
            for relationship in relationships
        ]
    )
