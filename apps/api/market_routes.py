from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import SignedIn
from apps.api.dto import CandleView, InstrumentDetailView, MarketRowView, MarketsView
from wallybot.application.market_overview import build_instrument_detail

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


@router.get("/markets/{instrument_id:path}", response_model=InstrumentDetailView)
async def market_detail(
    instrument_id: str, request: Request, user: SignedIn
) -> InstrumentDetailView:
    """Candles/volume/quality for one instrument -- `instrument_id` is `Instrument.id`
    (`"<venue>:<market_type>:<base>/<quote>"`), hence the `:path` converter so the embedded `/`
    doesn't get split as an extra path segment. Reuses the exact same provider/timeframe/quality
    policy `GET /api/markets` already uses (`app.state.market_overview`'s own bound kwargs),
    rather than a second, potentially-drifting configuration.
    """
    kwargs = request.app.state.market_overview.keywords
    detail = await build_instrument_detail(
        provider=kwargs["provider"],
        clock=kwargs["clock"],
        instrument_id=instrument_id,
        timeframe=kwargs["timeframe"],
        history_candles=kwargs["history_candles"],
        universe_config=kwargs["universe_config"],
        quality_policy=kwargs["quality_policy"],
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Unknown instrument")
    return InstrumentDetailView(
        id=detail.instrument.id,
        venue=detail.instrument.venue,
        base=detail.instrument.base,
        quote=detail.instrument.quote,
        as_of=detail.as_of.isoformat(),
        bid=str(detail.bid),
        ask=str(detail.ask),
        spread_ratio=str((detail.ask - detail.bid) / detail.ask),
        quality_status=detail.quality.status.value,
        quality_reasons=[f"{i.reason}: {i.evidence}" for i in detail.quality.issues],
        eligible=detail.eligible,
        rejection_reasons=list(detail.reasons),
        candles=[
            CandleView(
                open_time=candle.open_time.isoformat(),
                close_time=candle.close_time.isoformat(),
                open=str(candle.open),
                high=str(candle.high),
                low=str(candle.low),
                close=str(candle.close),
                volume=str(candle.volume),
            )
            for candle in detail.candles
        ],
    )
