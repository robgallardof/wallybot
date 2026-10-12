import csv
import io
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from apps.api.dependencies import Protected, SignedIn
from apps.api.dto import (
    BacktestBootstrapView,
    BacktestHistoryRowView,
    BacktestHistoryView,
    BacktestRunView,
    BacktestWalkForwardWindowView,
)
from apps.api.schemas import BacktestRun
from wallybot.application.backtest_orchestrator import BacktestRequest
from wallybot.infrastructure.experiment_repository import ExperimentRepository
from wallybot.strategies.trend_following import STRATEGY_ID

router = APIRouter(prefix="/api/backtests", tags=["backtests"])


# These are intentionally the complete reproducibility inputs and outcome summary from the
# immutable experiment record.  The regular history endpoint stays compact for the dashboard;
# an export must carry the versions, market rules, cost model and seed needed to audit a result.
EXPORT_FIELDS: tuple[str, ...] = (
    "experiment_id",
    "strategy_id",
    "strategy_version",
    "feature_engine_version",
    "backtest_engine_version",
    "instrument_venue",
    "instrument_market_type",
    "instrument_base",
    "instrument_quote",
    "price_increment",
    "quantity_increment",
    "min_quantity",
    "timeframe",
    "window_start",
    "window_end",
    "feature_window",
    "risk_off_threshold",
    "fee_rate",
    "slippage_pct",
    "starting_equity",
    "allocation_pct",
    "seed",
    "trade_count",
    "final_equity",
    "total_return_pct",
    "max_drawdown_pct",
    "win_rate",
    "created_at",
)


def _export_row(record: object) -> dict[str, str | int | None]:
    # `ExperimentRecord` deliberately uses Decimal/datetime domain values. Convert only at this
    # HTTP boundary so CSV and JSON do not lose precision or timezone information.
    from wallybot.domain.experiment import ExperimentRecord

    assert isinstance(record, ExperimentRecord)
    return {
        "experiment_id": record.experiment_id,
        "strategy_id": record.strategy_id,
        "strategy_version": record.strategy_version,
        "feature_engine_version": record.feature_engine_version,
        "backtest_engine_version": record.backtest_engine_version,
        "instrument_venue": record.instrument_venue,
        "instrument_market_type": record.instrument_market_type,
        "instrument_base": record.instrument_base,
        "instrument_quote": record.instrument_quote,
        "price_increment": str(record.price_increment),
        "quantity_increment": str(record.quantity_increment),
        "min_quantity": str(record.min_quantity),
        "timeframe": record.timeframe,
        "window_start": record.window_start.isoformat(),
        "window_end": record.window_end.isoformat(),
        "feature_window": record.feature_window,
        "risk_off_threshold": str(record.risk_off_threshold),
        "fee_rate": str(record.fee_rate),
        "slippage_pct": str(record.slippage_pct),
        "starting_equity": str(record.starting_equity),
        "allocation_pct": str(record.allocation_pct),
        "seed": record.seed,
        "trade_count": record.trade_count,
        "final_equity": str(record.final_equity),
        "total_return_pct": str(record.total_return_pct),
        "max_drawdown_pct": str(record.max_drawdown_pct),
        "win_rate": str(record.win_rate) if record.win_rate is not None else None,
        "created_at": record.created_at.isoformat(),
    }


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
                walk_forward_windows=body.walk_forward_windows,
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
        walk_forward=(
            [
                BacktestWalkForwardWindowView(
                    index=window.index,
                    trade_count=len(window.result.trades),
                    final_equity=str(window.result.final_equity),
                    total_return_pct=str(window.result.total_return_pct),
                    max_drawdown_pct=str(window.result.max_drawdown_pct),
                    win_rate=(
                        str(window.result.win_rate)
                        if window.result.win_rate is not None
                        else None
                    ),
                )
                for window in outcome.walk_forward
            ]
            if outcome.walk_forward is not None
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


@router.get("/export")
async def export_backtest_history(
    request: Request,
    user: SignedIn,
    format: str = "csv",
    experiment_id: str | None = None,
) -> Response:
    """Export immutable experiment inputs and results for independent review or re-runs."""
    if format not in {"csv", "json"}:
        raise HTTPException(status_code=422, detail="format must be csv or json")

    async with request.app.state.sessions() as db:
        repository = ExperimentRepository(db)
        if experiment_id is None:
            records = await repository.list_recent(STRATEGY_ID)
        else:
            record = await repository.get(experiment_id)
            # Never allow the filter to turn this into an oracle for another strategy's data.
            records = (record,) if record is not None and record.strategy_id == STRATEGY_ID else ()
    rows = [_export_row(record) for record in records]
    headers = {"Content-Disposition": f'attachment; filename="wallybot-backtests.{format}"'}
    if format == "json":
        return Response(
            content=json.dumps(rows, separators=(",", ":")),
            media_type="application/json",
            headers=headers,
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return Response(content=output.getvalue(), media_type="text/csv", headers=headers)
