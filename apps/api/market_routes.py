from fastapi import APIRouter, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import MarketRowView, MarketsView

router = APIRouter(prefix="/api", tags=["markets"])


@router.get("/markets", response_model=MarketsView)
async def markets(request: Request, user: SignedIn) -> MarketsView:
    overview = await request.app.state.market_overview()
    return MarketsView(
        as_of=overview.as_of.isoformat(),
        rows=[
            MarketRowView(
                id=row.instrument.id,
                venue=row.instrument.venue,
                base=row.instrument.base,
                quote=row.instrument.quote,
                bid=str(row.bid),
                ask=str(row.ask),
                spread_ratio=str((row.ask - row.bid) / row.ask),
                quality_status=row.quality.status,
                quality_reasons=[f"{i.reason}: {i.evidence}" for i in row.quality.issues],
                eligible=row.eligible,
                rejection_reasons=list(row.reasons),
                score=str(row.score) if row.score is not None else None,
                rank=row.rank,
            )
            for row in overview.rows
        ],
    )
