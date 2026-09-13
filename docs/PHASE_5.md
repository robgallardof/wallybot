# Phase 5 implementation backlog: datasets, backtests and evaluation

Status: Slices 1-4 delivered 2026-09-13. Per ARCHITECTURE.md's implementation sequence: "Immutable
datasets, backtests, walk-forward, Monte Carlo, benchmarks." Per PENDING.md's own recommended
delivery order this is the natural next major body of work after Phase 4 (PAPER execution) and
Phase 12 Slices 1-3 (AI proposals in SHADOW mode) — "mercado visible y calidad → decisión
persistida → PAPER con ledger y recuperación → **evaluación reproducible** → ...". Each slice gets
its own design pass when started, same discipline as every phase before it.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | DuckDB reader over ADR-005's checksummed Parquet manifests | Unit tests: round-trip, range filtering, tamper/schema-version rejection |
| 2 | Backtest engine: fills/costs model shared with PAPER, deterministic replay | Unit + property tests against hand-built series |
| 3 | Walk-forward, Monte Carlo/bootstrap evaluation with reported uncertainty | Unit tests against synthetic distributions |
| 4 | Experiment record (dataset/code/config/seed) + strategy registry lifecycle | Integration tests: insert-only history, reproducibility from artifacts |
| 5 | Backtest/experiment UI | Playwright: loading/error/empty states, ES/EN |

**This session implements Slices 1-4.**

## Delivered: Slice 1 — DuckDB reader over checksummed Parquet manifests

Per PENDING.md's Phase 5 first bullet: "Consultar Parquet con DuckDB usando manifiestos
inmutables, hashes, límites de recursos y versiones de esquema." `HistoricalStore` (Phase 2 Slice
5) already writes immutable, checksummed partitions with a sidecar manifest — nothing ever read
them back until this slice.

- Added `duckdb` and `pytz` (a real DuckDB Python-client dependency for TIMESTAMPTZ parameter
  binding, not optional) to the project.
- `wallybot/data/historical_query.py`: `read_candles(root, instrument, timeframe, start, end,
  limits)`. Every `*.manifest.json` under the requested partition tree has its recorded `sha256`
  re-verified against the actual Parquet file on disk **before** that file is ever queried —
  ADR-005's "checksummed manifests" enforced as a real gate, not just a fact the writer records.
  A manifest whose `schema_version` doesn't match this reader's `SUPPORTED_SCHEMA_VERSION` raises
  `UnsupportedSchemaVersion` outright rather than guessing a column mapping. `QueryResourceLimits`
  (memory/thread ceiling) is applied to every DuckDB connection, freshly opened and closed per
  call — never a shared long-lived process per PENDING.md's "límites de recursos."
- **Real design correction made while building this**: the first draft tried to reconstruct a
  full `Instrument` (including `price_increment`/`quantity_increment`/`min_quantity`) from Parquet
  columns alone — those fields were never written to Parquet (only venue/market_type/base/quote
  identity is), so this would have fabricated precision data, the exact mistake
  `TradeProposalRepository`'s docstring already documents avoiding. Fixed by having the caller
  pass the real `Instrument` it already has (from an exchange adapter), with each row's own
  identity columns checked against it defensively (`PartitionIdentityMismatch`) rather than a
  fabricated source of truth.
- **A real bug found and fixed via actual test execution, not guessed**: DuckDB's Python client
  converts `TIMESTAMPTZ` columns to the *host's local timezone* on fetch by default — silently
  shifting every UTC boundary this codebase relies on. Fixed with an explicit `SET
  TimeZone='UTC'` on every connection; caught because the first test run against a real
  Testcontainers-free `tmp_path` fixture returned `America/Mexico_City`-shifted timestamps instead
  of UTC ones on this development machine.
- `tests/unit/test_historical_query.py`: round-trip against a real `HistoricalStore`-written
  partition, range filtering (a candle counts only when it fully closes within the window, same
  "no partial future observation" rule `FeatureEngine` already enforces), a missing partition
  directory returning `[]` rather than an error, naive-datetime and end-before-start rejection, a
  tampered Parquet file being rejected even though its manifest still parses fine, and an
  unsupported schema version being rejected.

**Explicitly not built in this slice**: any actual backtest engine, fills/cost model, or
walk-forward/Monte Carlo evaluation (Slices 2-3); any experiment/strategy-registry persistence
(Slice 4); any UI (Slice 5); querying anything other than candles (features/quality/scanner
history are not yet written to Parquet at all — only `Candle` rows are).

Verified: full suite 460 passed (452→460), ruff/pyright clean.

## Delivered: Slice 2 — backtest engine (fills/costs model shared with PAPER)

Per ARCHITECTURE.md: "Implementar backtesting con modelo de fills y costes explícito; compartir
reglas verificables con PAPER." `wallybot/backtest/engine.py`'s `BacktestEngine`: single-
instrument, single-strategy, long-only replay over a `list[Candle]` (from Slice 1's
`read_candles`, or any other source honoring the same shape). At each candle, computes a
`FeatureVector` via the injected `FeatureEngine` using only candles up to and including that one
(`LookaheadError` already enforces this at the feature layer), classifies the regime, and asks
the injected `Strategy` for a signal — the exact same composition `DecisionPipeline` uses, not a
second parallel decision path.

**Fill assumption stated plainly, not hidden in a formula**: this codebase's Parquet store only
records OHLCV, never order-book depth or bid/ask, so there is no real spread to simulate against.
A signal computed as-of candle *i*'s close fills at candle *i+1*'s open — never the signal
candle's own price, which would be a lookahead bug. `BacktestCostModel.fee_rate` defaults to
`FakeExchange`'s own `0.001`, so PAPER and backtests share one fee assumption instead of two
independently invented ones; `slippage_pct` has no PAPER equivalent to share (FakeExchange
simulates a real bid/ask spread instead) and is an explicitly-labeled placeholder, exactly like
`smart_money.py`'s 60/40 split is labeled a placeholder, not a calibration.

`tests/unit/test_backtest_engine.py`: a hand-built rise-then-fall candle series produces exactly
one round-trip trade with the exact expected entry/exit fill prices (verified against
`TrendFollowingStrategy`'s real momentum/regime logic, not a mocked strategy); fee and slippage
are shown to actually shift fill prices and worsen PnL versus the zero-cost case; a flat series
produces zero trades and zero drawdown; mixed-instrument, too-short-series, non-positive-equity
and out-of-range-allocation inputs are all rejected. All 9 tests passed on first execution — the
fill-price arithmetic was hand-derived before running, not adjusted to match unexpected output.

**Explicitly not built**: walk-forward/Monte Carlo evaluation (Slice 3), multi-asset or
multi-strategy portfolios, any risk-engine sizing (this allocates a fixed `allocation_pct` of
current equity per trade and nothing else), short selling, any persistence of results (Slice 4).

Verified: full suite 469 passed (460→469), ruff/pyright clean.

## Delivered: Slice 3 — walk-forward segmentation + bootstrap resampling

Per ARCHITECTURE.md: "Implementar walk-forward, Monte Carlo y bootstrapping, con muestra e
incertidumbre reportadas." `wallybot/backtest/evaluation.py`:

- `run_walk_forward(engine, candles, starting_equity, allocation_pct, num_windows)`: splits the
  candle series into `num_windows` sequential, non-overlapping segments and re-runs
  `BacktestEngine` on each independently from the same `starting_equity` — **`TrendFollowing
  Strategy` has no tunable parameters to fit per period**, so this reports per-period robustness
  (does the same strategy hold up across different sub-windows) rather than a train/optimize/test
  parameter search, which only becomes meaningful once a strategy actually has parameters —
  documented as future work, not silently approximated.
- `bootstrap_trade_pnls(result, num_samples, seed)`: resamples a backtest's own realized trade
  PnLs with replacement (reshuffling which trades count, never inventing new ones) using a seeded
  `random.Random`, the same determinism idiom `FakeExchange` already uses. Returns `None` — not a
  fabricated distribution — for fewer than 2 trades, since a "distribution" over 0-1 outcomes is
  not evidence of anything. Reports mean/median/p05/p95 total PnL and probability of a net loss
  across the resampled totals.

`tests/unit/test_backtest_evaluation.py`: walk-forward produces exactly the requested window
count with correct independent starting equity each time, and rejects too-few-candles-per-window
and non-positive window counts; bootstrap converges toward the real per-trade mean over 5000
samples, is exactly deterministic for a fixed seed, reports `probability_of_loss == 1` when every
real trade lost, and returns `None` under 2 trades. All 8 tests passed on first run.

**Explicitly not built**: any parameter-fitting walk-forward (no strategy has tunable parameters
yet), leakage/survivorship-bias controls (Slice 3's remaining bullets), experiment/registry
persistence or UI (Slices 4-5).

Verified: full suite 477 passed (469→477), ruff/pyright clean.

## Delivered: Slice 4 — experiment record persistence

Per ARCHITECTURE.md: "Registrar dataset, código, dependencias, configuración, semilla y
divisiones temporales de cada experimento." `wallybot/domain/experiment.py`'s `ExperimentRecord`
(pure domain type) captures exactly what a re-run needs to reproduce a backtest: dataset window
(instrument identity + timeframe + start/end -- not the candles themselves, which live in
Slice 1's checksummed Parquet), code identity (strategy id/version, feature-engine version,
backtest-engine version), configuration (feature window, risk-off threshold, cost model,
allocation) and the bootstrap seed (`None` for a plain deterministic backtest with no resampling).
The result summary (final equity, return, drawdown, win rate, trade count) is stored alongside so
a later re-run can be *compared* against it, not just re-derived. `migrations/versions/
0015_experiment_records.py` + `ExperimentRecordRow` + `wallybot/infrastructure/
experiment_repository.py`'s `ExperimentRepository`: insert-only, and — unlike
`TradeProposalRepository`/`ShadowDecisionRepository` — **fully round-trips**, since this table
never stores an `Instrument`-shaped value, only plain identity strings a caller already has, so
there is no fabrication risk to design around.

**Real infrastructure bug found and fixed via an actual Docker build, not assumed**: adding
`duckdb` as a base dependency (Slice 1) broke `docker compose build` — Alpine's musl libc has no
prebuilt DuckDB wheel, so `uv sync` tried to compile it from source and failed with `CMake Error:
... Could not find the compiler specified in the environment variable CXX`. Fixed by moving
`duckdb`/`pytz` into their own `research` dependency-group (`[tool.uv] default-groups = ["dev",
"research"]` keeps them available for local dev and CI's `uv run pytest`, which runs on
glibc/Ubuntu) and excluding that group from `docker/api.Dockerfile`'s two `uv sync` calls
(`--no-group research`) — backtesting has no scheduler-wired caller yet, so no running service
container needs it. Verified end-to-end: `docker compose build api` now succeeds, the container
starts, and `/health/ready` reports `ready` at the new migration head.

`tests/unit/test_experiment.py` (15 tests: validation of every field) and `tests/integration/
test_experiment_persistence.py` (round-trip equality, unknown-id lookup, two re-runs of the same
strategy both persist as independent history rather than overwriting).

**Explicitly not built**: any strategy-registry lifecycle (DRAFT → BACKTESTED → VALIDATED → ...,
still Slice 4's remaining bullet, not delivered here — this slice is experiment persistence only);
any code that actually calls `BacktestEngine`/`ExperimentRepository` together end-to-end (no
orchestrator wires dataset lookup → backtest → experiment save yet); any UI (Slice 5).

Verified: full suite 495 passed (477→495), ruff/pyright clean across the whole repo (two
pre-existing, unrelated pyright findings in `auth_routes.py`/`system_routes.py` predate this
session), `docker compose build`/`up`/`/health/ready` all verified against the live stack.
