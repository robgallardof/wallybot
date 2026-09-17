from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Protected, SignedIn
from apps.api.dto import (
    BacktestBootstrapView,
    BacktestHistoryRowView,
    BacktestHistoryView,
    BacktestRunView,
)
from apps.api.schemas import BacktestRun
from wallybot.application.backtest_orchestrator import BacktestRequest
from wallybot.infrastructure.experiment_repository import ExperimentRepository
from wallybot.strategies.trend_following import STRATEGY_ID

router = APIRouter(prefix="/api/backtests", tags=["backtests"])


@router.post("", response_model=BacktestRunView)
async def run_backtest(body: BacktestRun, request: Request, user: Protected) -> BacktestRunView:
    orchestrator = request.app.state.backtest_orchestrator
    try:
        outcome = await orchestrator.run(
            BacktestRequest(
                instrument_base=body.instrument_base,
                instrument_quote=body.instrument_quote,
                timeframe=body.timeframe,
                window_start=body.window_start,
                window_end=body.window_end,
                feature_window=body.feature_window,
                risk_off_threshold=body.risk_off_threshold,
                starting_equity=body.starting_equity,
                allocation_pct=body.allocation_pct,
                fee_rate=body.fee_rate,
                slippage_pct=body.slippage_pct,
                bootstrap_seed=body.bootstrap_seed,
                bootstrap_samples=body.bootstrap_samples,
            )
        )
    except ValueError as exc:
        # Covers InstrumentNotFound/InsufficientHistoricalData (both ValueError subclasses) and
        # any other domain validation raised while composing the engine -- all honest 422s about
        # the requested dataset/config, never a fabricated result.
        detail = str(exc)
        if "got 0" in detail:
            detail = (
                "No hay velas históricas para el período seleccionado. "
                "Usa el marco de 1 hora y el rango sugerido; la carga de mercado puede tardar "
                "unos minutos después de iniciar la instancia. "
                f"Detalle técnico: {detail}"
            )
        raise HTTPException(status_code=422, detail=detail) from exc

    async with request.app.state.sessions.begin() as db:
        await ExperimentRepository(db).save(outcome.record)

    record = outcome.record
    bootstrap = outcome.bootstrap
    return BacktestRunView(
        experiment_id=record.experiment_id,
        instrument_venue=record.instrument_venue,
        instrument_base=record.instrument_base,
        instrument_quote=record.instrument_quote,
        timeframe=record.timeframe,
        trade_count=record.trade_count,
        starting_equity=str(record.starting_equity),
        final_equity=str(record.final_equity),
        total_return_pct=str(record.total_return_pct),
        max_drawdown_pct=str(record.max_drawdown_pct),
        win_rate=str(record.win_rate) if record.win_rate is not None else None,
        created_at=record.created_at.isoformat(),
        bootstrap=(
            BacktestBootstrapView(
                sample_count=bootstrap.sample_count,
                trades_per_sample=bootstrap.trades_per_sample,
                mean_total_pnl=str(bootstrap.mean_total_pnl),
                median_total_pnl=str(bootstrap.median_total_pnl),
                p05_total_pnl=str(bootstrap.p05_total_pnl),
                p95_total_pnl=str(bootstrap.p95_total_pnl),
                probability_of_loss=str(bootstrap.probability_of_loss),
            )
            if bootstrap is not None
            else None
        ),
    )


@router.get("", response_model=BacktestHistoryView)
async def backtest_history(request: Request, user: SignedIn) -> BacktestHistoryView:
    async with request.app.state.sessions() as db:
        records = await ExperimentRepository(db).list_recent(STRATEGY_ID)
    return BacktestHistoryView(
        rows=[
            BacktestHistoryRowView(
                experiment_id=record.experiment_id,
                strategy_id=record.strategy_id,
                instrument_venue=record.instrument_venue,
                instrument_base=record.instrument_base,
                instrument_quote=record.instrument_quote,
                timeframe=record.timeframe,
                window_start=record.window_start.isoformat(),
                window_end=record.window_end.isoformat(),
                trade_count=record.trade_count,
                starting_equity=str(record.starting_equity),
                final_equity=str(record.final_equity),
                total_return_pct=str(record.total_return_pct),
                max_drawdown_pct=str(record.max_drawdown_pct),
                win_rate=str(record.win_rate) if record.win_rate is not None else None,
                created_at=record.created_at.isoformat(),
            )
            for record in records
        ]
    )
