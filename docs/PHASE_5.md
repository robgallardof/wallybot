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

## Delivered: Slice 5 — backtest/experiment UI

Per this table's own acceptance evidence: "Playwright: loading/error/empty states, ES/EN." Closes
the gap every earlier slice's "Explicitly not built" section flagged: "no code that actually calls
`BacktestEngine`/`ExperimentRepository` together end-to-end" -- until this slice, nothing wired
Slices 1-4 into a runnable path, so there was no way to produce a real `ExperimentRecord` outside
a unit test, and therefore nothing genuine for a UI to show.

`wallybot/application/backtest_orchestrator.py`'s `BacktestOrchestrator.run()` is that missing
wiring: looks up the real `Instrument` from an injected `MarketDataProvider` (never fabricates
price/quantity increments from caller-supplied numbers -- the same discipline
`historical_query.py` already documents), calls Slice 1's `read_candles` (via `asyncio.to_thread`,
since DuckDB's query is blocking), runs Slice 2's `BacktestEngine`, optionally Slice 3's
`bootstrap_trade_pnls`, and returns a pure `ExperimentRecord` for the caller to persist --
deliberately DB-free itself, same separation `ShadowDecisionService` already uses (persistence is
the API route's job, the one place that already owns a session).

`POST /api/backtests` (`apps/api/backtest_routes.py`, CSRF-protected like `/api/control`, any
signed-in role -- this is research, not a risk/execution action) runs a real backtest and persists
the resulting `ExperimentRecord`; `GET /api/backtests` lists recent history
(`ExperimentRepository.list_recent("trend_following")` -- this codebase has exactly one strategy,
so no new listing method was needed). Both a missing instrument and an under-sized dataset window
come back as a clear 422 with the real domain message, never a fabricated empty result.

**Real access-control gap found and fixed, same recurring pattern as 0012/0013/0016** --
`migrations/versions/0017_backtest_api_grants.py`: `wally_api` had no grant at all on
`experiment_records` (only `wally_worker`/`wally_research` did, from Slice 4). This one had an
extra wrinkle none of the earlier grant-gap fixes did: `experiment_records` is the first API-write
table with a Postgres-generated (`SERIAL`) surrogate `id` -- every other table `wally_api` has ever
inserted into (`events`, `users`, ...) uses an app-generated UUID string instead. `GRANT INSERT` on
the table alone does not include `USAGE` on the sequence backing that column's `nextval()` default;
without it, `POST /api/backtests` fails with "permission denied for sequence
experiment_records_id_seq" even though the table grant looks sufficient. Found by writing the
integration test against the real `wally_api`-scoped role (every earlier Phase 5 persistence test
used the Postgres owner connection directly, per Slice 1-4's own test fixtures, so none of them
could have caught this), not guessed. Bumped `apps/api/main.py`'s hardcoded Alembic revision check
to `"0017_backtest_api_grants"` (same recurring rough edge as every migration before it).

Frontend: `apps/web/src/components/dashboard/pages/BacktestsPage.tsx` -- a trigger form (instrument
base/quote as free text, since real Kraken pairs use Kraken's own asset codes like `XBT`, not
`BTC`) plus a result panel and a history table, replacing the "research" nav slot's previous
`Unavailable` placeholder (its own copy already said "Los experimentos y backtests reproducibles
se incorporan en la fase 5" -- this is that promise kept). `useBacktestsData.ts` pairs a
`useQuery` (history) with a `useMutation` (run), the first mutation hook in this codebase's
`apps/web/src/hooks/` beyond the dashboard's existing `/control` pattern.
`tests/integration/test_backtest_route.py` (Testcontainers, real Parquet fixture written via
`HistoricalStore`, `FakeExchange` injected the same way `test_markets_route.py` already does so
this mandatory test never depends on live Kraken) and a new Playwright test in
`observability.spec.ts` (loading → empty → run → history refresh → 422-as-alert).

**Explicitly not built**: any dataset ingestion job that actually writes to the Parquet store in
production -- confirmed via `graphify query` that `HistoricalStore.write_partition` has no caller
outside test code anywhere in this codebase, a pre-existing gap from Phase 2 Slice 5, not something
this slice introduced or was scoped to fix. `WALLY_HISTORICAL_DATA_ROOT` (new `Settings` field,
default `/data/historical`) has no corresponding Docker volume yet either, on purpose: the `api`
container is `read_only: true` with no writer for that path today, so mounting an empty volume now
would be exactly the kind of placeholder infrastructure `ARCHITECTURE.md` says to avoid ("create
modules when a real capability needs them"). Until a real ingestion job exists, `POST /api/backtests`
against a real deployment will honestly 422 with "insufficient historical data" for any window --
that is the correct behavior given the data genuinely isn't there, not a bug in this slice. Also
not built: a strategy registry (this only ever runs `TrendFollowingStrategy` -- Phase 5 Slice 4's
still-open "strategy registry lifecycle" bullet), and any UI to re-run/compare two experiments
side by side.

Verified: full suite 510 passed (501→510, `test_backtest_orchestrator.py` +
`test_backtest_route.py`), ruff/pyright clean on every new/changed file (the same two pre-existing,
unrelated `auth_routes.py`/`system_routes.py` pyright findings from Slice 4 are untouched),
domain purity confirmed (`backtest_orchestrator.py` imports only stdlib + existing
`wallybot.backtest`/`wallybot.data`/`wallybot.domain`/`wallybot.features`/`wallybot.strategies`
modules -- it lives in `wallybot/application/`, not `wallybot/domain/`, precisely because it
composes I/O). Frontend: `tsc --noEmit`, `eslint`, `next build` all clean; full Playwright suite
(8 passed, 1 pre-existing production-only test skipped in this run mode) including the new
backtests test.

**Real deployment bug found and fixed via an actual container start, not assumed**: the first
`docker compose up -d api` after this slice crash-looped --
`ModuleNotFoundError: No module named 'duckdb'`. `apps/api/main.py` now imports
`backtest_orchestrator.py` at module load (to build `app.state.backtest_orchestrator`), which
imports `wallybot/data/historical_query.py`, which imports `duckdb` -- and Slice 4's own dependency
split had deliberately kept `duckdb`/`pytz` out of the Alpine runtime image precisely because
"backtesting is research/dev tooling for now, not something any running service container calls."
This slice makes that no longer true for the `api` process. Confirmed live against PyPI that
`duckdb` (pinned `>=1.5.5`) still ships no `musllinux` wheel, so installing it into the existing
Alpine image would mean compiling from source -- not viable in a normal build. Per ADR-012's own
anticipated follow-up ("later numerical/research libraries may justify a separate glibc research
image when their wheel support requires it"), `docker/api.Dockerfile` gained a second,
`python:3.12.14-slim`-based `runtime-research` target; only the `api` and `research`
(research_worker) compose services build from it (`wallybot-api-research:0.1.0`), while
`worker`/`scheduler` stay on the original Alpine `runtime` target unchanged, since neither touches
DuckDB. Verified end-to-end: `docker compose build api research` succeeds, both containers start
and stay healthy, `/health/ready` reports `ready` at migration head `0017_backtest_api_grants`.
See ADR-012's "Update 2026-09-13" section for the full record.

**Phase 5 status: all 5 slices delivered as this table originally scoped them.** The
still-open "strategy registry lifecycle" bullet from Slice 4 remains open -- meaningful only once
a second strategy exists to register.
