"""Walk-forward segmentation and bootstrap resampling over `BacktestEngine` output, per
ARCHITECTURE.md's Phase 5 bullet: "Implementar walk-forward, Monte Carlo y bootstrapping, con
muestra e incertidumbre reportadas."

Walk-forward here means sequential, non-overlapping out-of-sample sub-periods, each re-run from
`starting_equity` independently (never compounding one period's ending equity into the next) --
`TrendFollowingStrategy` has no tunable parameters to fit per period, so this reports per-period
robustness (does the same strategy hold up across different sub-windows) rather than a
train/optimize/test parameter search, which is future work once a strategy actually has
parameters to fit.

Bootstrap resampling draws, with replacement, from a backtest's own realized trade PnLs --
reshuffling the *order and selection* of trades that already happened, not inventing new ones --
using a seeded `random.Random` for reproducibility, the same determinism idiom `FakeExchange`
already uses. This estimates how sensitive the aggregate result is to which trades happened to
occur, not a claim about future returns.
"""

import random
import statistics
from dataclasses import dataclass
from decimal import Decimal

from wallybot.backtest.engine import BacktestEngine, BacktestResult
from wallybot.domain.market import Candle

EVALUATION_VERSION = 1


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    result: BacktestResult


@dataclass(frozen=True)
class BootstrapResult:
    version: int
    sample_count: int
    trades_per_sample: int
    mean_total_pnl: Decimal
    median_total_pnl: Decimal
    p05_total_pnl: Decimal
    p95_total_pnl: Decimal
    probability_of_loss: Decimal


def run_walk_forward(
    engine: BacktestEngine,
    candles: list[Candle],
    starting_equity: Decimal,
    allocation_pct: Decimal,
    num_windows: int,
) -> tuple[WalkForwardWindow, ...]:
    if num_windows < 1:
        raise ValueError("num_windows must be positive")
    ordered = sorted(candles, key=lambda c: c.open_time)
    min_needed = engine.feature_window + 2
    window_size = len(ordered) // num_windows
    if window_size < min_needed:
        raise ValueError(
            f"each of {num_windows} windows needs at least {min_needed} candles, "
            f"but {len(ordered)} candles only gives {window_size} per window"
        )

    windows = []
    for index in range(num_windows):
        start_idx = index * window_size
        end_idx = start_idx + window_size if index < num_windows - 1 else len(ordered)
        segment = ordered[start_idx:end_idx]
        result = engine.run(segment, starting_equity, allocation_pct)
        windows.append(WalkForwardWindow(index=index, result=result))
    return tuple(windows)


def bootstrap_trade_pnls(
    result: BacktestResult, num_samples: int, seed: int
) -> BootstrapResult | None:
    """`None` when there are fewer than 2 trades -- a bootstrap over 0 or 1 realized outcomes
    reports a false sense of a distribution rather than an honest "not enough data"."""
    if num_samples < 1:
        raise ValueError("num_samples must be positive")
    trades = result.trades
    if len(trades) < 2:
        return None

    rng = random.Random(seed)
    pnls = [trade.pnl for trade in trades]
    totals = [sum(rng.choices(pnls, k=len(pnls)), Decimal(0)) for _ in range(num_samples)]
    totals.sort()

    return BootstrapResult(
        version=EVALUATION_VERSION,
        sample_count=num_samples,
        trades_per_sample=len(pnls),
        mean_total_pnl=sum(totals, Decimal(0)) / len(totals),
        median_total_pnl=statistics.median(totals),
        p05_total_pnl=totals[int(len(totals) * 0.05)],
        p95_total_pnl=totals[min(int(len(totals) * 0.95), len(totals) - 1)],
        probability_of_loss=Decimal(sum(1 for t in totals if t < 0)) / Decimal(len(totals)),
    )
