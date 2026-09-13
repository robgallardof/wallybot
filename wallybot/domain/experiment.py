"""ExperimentRecord: what a backtest run needs to be reproducible from its own artifacts, per
ARCHITECTURE.md's Phase 5 bullet: "Registrar dataset, código, dependencias, configuración, semilla
y divisiones temporales de cada experimento."

Every field here is something a re-run needs to reproduce the same result: which dataset window
(instrument identity + timeframe + start/end -- not the candles themselves, which live in ADR-005's
immutable, checksummed Parquet and are looked up by this same window), which code (strategy id and
version, feature-engine version, backtest-engine version -- all already-versioned per this
codebase's existing convention), which configuration (feature window, risk-off threshold, cost
model, allocation), and which random seed (bootstrap resampling only; a plain deterministic
backtest has none). The result summary is stored alongside so a later re-run can be *compared*
against it rather than only re-derived -- catching a silent regression in the engine itself, not
just re-proving the strategy "worked."

Pure domain: no framework imports, no I/O.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from wallybot.domain.validation import require_aware_datetime, require_unit_interval


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    strategy_id: str
    strategy_version: int
    feature_engine_version: int
    backtest_engine_version: int
    instrument_venue: str
    instrument_base: str
    instrument_quote: str
    timeframe: str
    window_start: datetime
    window_end: datetime
    feature_window: int
    risk_off_threshold: Decimal
    fee_rate: Decimal
    slippage_pct: Decimal
    starting_equity: Decimal
    allocation_pct: Decimal
    seed: int | None
    trade_count: int
    final_equity: Decimal
    total_return_pct: Decimal
    max_drawdown_pct: Decimal
    win_rate: Decimal | None
    created_at: datetime

    def __post_init__(self) -> None:
        for field, value in (
            ("experiment_id", self.experiment_id),
            ("strategy_id", self.strategy_id),
            ("instrument_venue", self.instrument_venue),
            ("instrument_base", self.instrument_base),
            ("instrument_quote", self.instrument_quote),
            ("timeframe", self.timeframe),
        ):
            if not value:
                raise ValueError(f"{field} is required")
        for field, value in (
            ("strategy_version", self.strategy_version),
            ("feature_engine_version", self.feature_engine_version),
            ("backtest_engine_version", self.backtest_engine_version),
            ("feature_window", self.feature_window),
        ):
            if value < 1:
                raise ValueError(f"{field} must be positive")
        require_aware_datetime(self.window_start, "window_start")
        require_aware_datetime(self.window_end, "window_end")
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.risk_off_threshold <= 0:
            raise ValueError("risk_off_threshold must be positive")
        for field, value in (("fee_rate", self.fee_rate), ("slippage_pct", self.slippage_pct)):
            if not (Decimal(0) <= value <= Decimal(1)):
                raise ValueError(f"{field} must be between 0 and 1")
        if self.starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        if not (Decimal(0) < self.allocation_pct <= Decimal(1)):
            raise ValueError("allocation_pct must be between 0 (exclusive) and 1")
        if self.trade_count < 0:
            raise ValueError("trade_count must be nonnegative")
        if self.final_equity < 0:
            raise ValueError("final_equity must be nonnegative")
        if self.max_drawdown_pct < 0:
            raise ValueError("max_drawdown_pct must be nonnegative")
        if self.win_rate is not None:
            require_unit_interval(self.win_rate, "win_rate")
        require_aware_datetime(self.created_at, "created_at")
