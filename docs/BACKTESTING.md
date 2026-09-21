# Backtesting: engine, evaluation, and what Monte Carlo actually means here

Status: a real, single-instrument, single-strategy, long-only backtest engine
(`wallybot/backtest/engine.py`) with an explicit fill/cost model, wired end to end through
`BacktestOrchestrator` (`wallybot/application/backtest_orchestrator.py`) to `POST /api/backtests`
and the Backtests UI. Walk-forward segmentation and bootstrap resampling
(`wallybot/backtest/evaluation.py`) both existed and were unit-tested in isolation before this
session; this session connected them to the orchestrator and the API as optional per-request
parameters. **True Monte Carlo — price-path simulation — is not built.** What this codebase calls
"bootstrap" resamples the PnLs of trades a backtest already realized; it is a materially different
thing from simulating new, hypothetical price paths, and this document says so explicitly rather
than letting the two blur together.

## The fill and cost model

`BacktestEngine` (`wallybot/backtest/engine.py`) replays historical candles bar-by-bar:

- A signal computed as-of a candle's `close_time` — using only that candle and everything before it
  (`FeatureEngine.compute` raises `LookaheadError` if ever handed a later one) — fills at the
  **next** candle's open price. There is no same-bar fill.
- Fill price includes `BacktestCostModel.slippage_pct` (default `0.0005`, applied against the
  entry/exit direction) — an explicitly-labeled placeholder, not a calibrated cost, per the
  engine's own docstring, "same honesty this codebase already applies to `smart_money.py`'s 60/40
  split." There is no PAPER-simulator equivalent to share it with, because `FakeExchange` simulates
  a real bid/ask spread instead of a flat slippage percentage.
- Fee rate (`BacktestCostModel.fee_rate`, default `0.001`) deliberately reuses `FakeExchange`'s own
  default, so PAPER and backtests share one fee assumption instead of two independently invented
  ones.
- **Why no real spread model:** this codebase's Parquet store (ADR-005) only records OHLCV candles,
  not order book depth or bid/ask — there is no real spread to simulate against. This is stated
  plainly in the engine's own docstring rather than silently approximated.
- Every cash amount (equity, fees, proceeds, cost basis) is quantized to cent precision after every
  step, and fill prices/quantities to the instrument's own `price_increment`/`quantity_increment`
  (quantity always rounds down). This exists specifically because unquantized `Decimal` division
  compounded into results like `final_equity` showing `"10999.93099135968523141293843"` — a real
  bug found from a user-reported screenshot, fixed by this quantization, not a hypothetical
  precision concern.
- **Long-only, single instrument, single strategy.** `Action.SELL` only ever exits an existing
  long — there is no short-selling anywhere in this codebase (matching `DecisionPipeline`'s own
  "SELL is not yet supported [as a short]" limit in the live loop, see [TRADING.md](TRADING.md)).
  Position sizing is a fixed `allocation_pct` of current equity per trade — the engine does not run
  `RiskEngine` sizing; it is a strategy-performance tool, not a risk-policy rehearsal.

`BacktestResult` reports `trades`, an `equity_curve`, `total_return_pct`, `max_drawdown_pct`
(computed from the equity curve's own running peak) and `win_rate`.

## Walk-forward segmentation

`run_walk_forward` (`wallybot/backtest/evaluation.py`) splits the requested candle range into
`num_windows` **sequential, non-overlapping** sub-periods and re-runs the full engine on each one
independently — starting from `starting_equity` fresh every window, never compounding one window's
ending equity into the next. The module's own docstring explains why this is not a real
train/optimize/test parameter search: `TrendFollowingStrategy` (the only strategy that exists —
see [STRATEGIES.md](STRATEGIES.md)) has no tunable parameters to fit per window, so this reports
per-period robustness (does the same fixed strategy hold up across different sub-windows of
history), not a fitted out-of-sample evaluation. A real parameter search becomes possible only once
a strategy actually has parameters to fit.

## Bootstrap resampling — not Monte Carlo

`bootstrap_trade_pnls` (`wallybot/backtest/evaluation.py`) draws, **with replacement**, from a
single backtest run's own realized trade PnLs, using a seeded `random.Random` for reproducibility.
It reshuffles the order and selection of trades that already happened — it does not invent new
trades, and it does not simulate a new price path. It returns `None` when there are fewer than two
realized trades, deliberately, "rather than report[ing] a false sense of a distribution." The
result (`BootstrapResult`) reports `mean`/`median`/`p05`/`p95` total PnL across the resampled
distribution and a `probability_of_loss`.

This estimates how sensitive the aggregate backtest result is to *which* trades happened to occur
and in what order — it says nothing about how the strategy would perform under price movements that
never occurred in the historical window. Real Monte Carlo for a trading strategy means simulating
new, synthetic price paths (via a stochastic price model, block-bootstrapped returns, or similar)
and re-running the strategy against each one. **That does not exist in this codebase.**
`docs/PENDING.md`'s own Fase 5 entry says this directly: "Monte Carlo real (simulación de
trayectorias de precio) sigue sin construirse — el bootstrap resamplea PnLs de operaciones ya
realizadas, no es lo mismo."

## Wiring: `BacktestOrchestrator` and the API

`BacktestOrchestrator.run` (`wallybot/application/backtest_orchestrator.py`) composes
`read_candles` → `BacktestEngine` → optional bootstrap/walk-forward into the one real path from a
requested dataset window to a comparable, persistable outcome. `bootstrap_seed` and
`walk_forward_windows` are both optional per request and independent of each other and of the main
result — a caller can ask for either, both, or neither. The orchestrator itself never persists
anything; it returns a pure `ExperimentRecord` for the caller (`POST /api/backtests` in
`apps/api/backtest_routes.py`) to save via `ExperimentRepository`. Only
`TrendFollowingStrategy`/`SimpleFeatureEngine` are wired — this codebase has exactly one strategy
and one feature engine, so there is no strategy-selection parameter on the request.

`POST /api/backtests` accepts `bootstrap_seed`/`bootstrap_samples`/`walk_forward_windows` directly
on the request body and returns the bootstrap/walk-forward results alongside the main backtest
result when requested. This is also the exact path `research_runner.py` re-runs for a research job
(see [RESEARCH.md](RESEARCH.md)) — a research re-run and a fresh backtest are the same engine, same
request shape, different caller.

## Historical data access

`read_candles` (`wallybot/data/historical_query.py`) is a pure, no-write DuckDB query layer over
ADR-005's checksummed Parquet partitions. Every manifest's recorded `sha256` is re-verified against
the file on disk before that partition is trusted; a manifest whose `schema_version` doesn't match
`SUPPORTED_SCHEMA_VERSION` is rejected outright rather than read with a guessed column mapping.
DuckDB is configured with an explicit memory/thread ceiling per query
(`QueryResourceLimits`, default 512MB / 2 threads), never inherited from a shared long-lived
process. The `Instrument` being queried is always supplied by the caller (never reconstructed from
Parquet columns, which only carry identity, not precision) — the same "never fabricate a precision
field" discipline `TradeProposalRepository` documents (see [AI.md](AI.md)).

## What is not built

- **True Monte Carlo (price-path simulation).** See above — this is the single most important gap
  on this page; do not read "bootstrap" as "Monte Carlo."
- **Leakage/survivorship controls.** `docs/PENDING.md` Fase 5's "Controlar leakage y sesgos de
  selección/supervivencia; documentar límites de historia y activos deslistados" is unchecked.
- **Strategy/portfolio attribution, benchmark comparison.** No BTC/ETH/cash/passive-portfolio
  comparison exists; no attribution by asset/regime/bucket.
- **A strategy registry or promotion lifecycle.** No DRAFT → BACKTESTED → VALIDATED → ... promotion
  workflow is implemented; `ExperimentRecord` rows are historical results, not promotion evidence
  with human sign-off.
- **Downloadable artifacts, experiment comparison UI.** The Backtests page shows history rows; there
  is no comparison view or artifact download beyond what the API response already returns.

See [DATA.md](../DATA.md) for the Parquet/manifest storage guarantees this reader enforces, and
[ARCHITECTURE.md](../ARCHITECTURE.md) for backtesting's place in the overall implementation
sequence (Phase 5).
