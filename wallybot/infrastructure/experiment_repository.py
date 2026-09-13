"""ExperimentRepository: insert-only persistence for `wallybot.domain.experiment.ExperimentRecord`.

`save` always inserts a new row -- a re-run with the same configuration is a new fact to compare
against the old one, never an overwrite. Unlike `TradeProposalRepository`, this table stores no
`Instrument`-shaped value at all (only plain venue/base/quote identity strings), so `get`/`list_
recent` fully reconstruct the domain object with no fabrication concern.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.experiment import ExperimentRecord
from wallybot.infrastructure.models import ExperimentRecordRow


class ExperimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, record: ExperimentRecord) -> None:
        self.session.add(
            ExperimentRecordRow(
                experiment_id=record.experiment_id,
                strategy_id=record.strategy_id,
                strategy_version=record.strategy_version,
                feature_engine_version=record.feature_engine_version,
                backtest_engine_version=record.backtest_engine_version,
                instrument_venue=record.instrument_venue,
                instrument_base=record.instrument_base,
                instrument_quote=record.instrument_quote,
                timeframe=record.timeframe,
                window_start=record.window_start,
                window_end=record.window_end,
                feature_window=record.feature_window,
                risk_off_threshold=record.risk_off_threshold,
                fee_rate=record.fee_rate,
                slippage_pct=record.slippage_pct,
                starting_equity=record.starting_equity,
                allocation_pct=record.allocation_pct,
                seed=record.seed,
                trade_count=record.trade_count,
                final_equity=record.final_equity,
                total_return_pct=record.total_return_pct,
                max_drawdown_pct=record.max_drawdown_pct,
                win_rate=record.win_rate,
                created_at=record.created_at,
            )
        )

    async def get(self, experiment_id: str) -> ExperimentRecord | None:
        row = (
            await self.session.execute(
                select(ExperimentRecordRow).where(
                    ExperimentRecordRow.experiment_id == experiment_id
                )
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def list_recent(self, strategy_id: str) -> tuple[ExperimentRecord, ...]:
        rows = (
            (
                await self.session.execute(
                    select(ExperimentRecordRow)
                    .where(ExperimentRecordRow.strategy_id == strategy_id)
                    .order_by(ExperimentRecordRow.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: ExperimentRecordRow) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id=row.experiment_id,
            strategy_id=row.strategy_id,
            strategy_version=row.strategy_version,
            feature_engine_version=row.feature_engine_version,
            backtest_engine_version=row.backtest_engine_version,
            instrument_venue=row.instrument_venue,
            instrument_base=row.instrument_base,
            instrument_quote=row.instrument_quote,
            timeframe=row.timeframe,
            window_start=row.window_start,
            window_end=row.window_end,
            feature_window=row.feature_window,
            risk_off_threshold=row.risk_off_threshold,
            fee_rate=row.fee_rate,
            slippage_pct=row.slippage_pct,
            starting_equity=row.starting_equity,
            allocation_pct=row.allocation_pct,
            seed=row.seed,
            trade_count=row.trade_count,
            final_equity=row.final_equity,
            total_return_pct=row.total_return_pct,
            max_drawdown_pct=row.max_drawdown_pct,
            win_rate=row.win_rate,
            created_at=row.created_at,
        )
