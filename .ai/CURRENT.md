# Current task

**Task:** Continue closing the "backend exists, nothing shows it" gap per `docs/PENDING.md`'s
recommended delivery order. User said "Continua con el flow y la app ok?" — kept going
autonomously per this session's established pattern (no check-in between slices).

## Latest slice — Parquet ingestion job verified end-to-end + a durability bug fixed (2026-09-16)

The Parquet dataset-ingestion job (`wallybot/application/market_ingestion.py`,
`HistoricalIngestionCursorRepository`, migration `0019_historical_ingestion_cursor`, the
`_market_ingestion_loop` background task in `apps/api/main.py`'s lifespan, and the
`historical_data` Docker volume) was already implemented and unit/integration tested from earlier
in this session — but not yet verified against the real running stack, and not documented here.
This slice did that verification and found + fixed a real bug:

- Rebuilt `wallybot-api:0.1.0` (base, used by `migrate`/`worker`/`scheduler`) and
  `wallybot-api-research:0.1.0` (used by `api`/`research`) — both needed, same lesson as the
  0018 slice. Ran `docker compose up migrate` (applied `0019` cleanly), force-recreated `api`,
  confirmed `/health/ready` → `{"status":"ready"}` at `0019_historical_ingestion_cursor`.
- **Found a real durability bug** while checking the result: `HistoricalStore._write_parquet` /
  `_write_manifest` wrote to a `.tmp-*` file and used `os.replace` for atomicity, but never
  `fsync`'d before the rename. On this host, a prior run (~17h earlier, same session, before this
  slice) left **60 zero-byte "published" partitions** (30 dates × XBT_USD/ETH_USD) sitting under
  `/data/historical` — `os.replace` had completed (so the corrupted file has the final, non-tmp
  name) but the write's dirty pages never made it to the volume's backing disk, most likely
  because the Docker Desktop VM was paused/resumed (laptop sleep) between the write and now.
  A single corrupted file breaks DuckDB's `read_parquet(glob)` for the *whole* instrument
  (`InvalidInputException`), so this wasn't just "missing data", it was "broken backtests".
  Fixed in `wallybot/data/historical.py`: both writers now open the tmp file explicitly,
  `flush()` + `os.fsync(fd)` before `os.replace`. Rebuilt/redeployed `api` with the fix.
- User explicitly chose (asked via AskUserQuestion) to delete the 60 corrupted files but
  **not** reset the ingestion cursor — the cursor already advanced past those dates when the
  original (corrupted) write "succeeded", so normal hourly ingestion will **not** backfill
  Aug 17–Sep 15. XBT_USD/ETH_USD 1h data now starts fresh from 2026-09-16 03:00 and grows one
  candle/hour going forward (verified via DuckDB inside the `api` container after cleanup: 17
  rows each, `InvalidInputException` gone). **If a fuller backtest window is needed later,
  delete the two rows in `historical_ingestion_cursors` for `(kraken:SPOT:BTC/USD, 1h)` and
  `(kraken:SPOT:ETH/USD, 1h)` to force a bootstrap re-fetch (720h lookback) — nobody has asked
  for that yet.**
- Verified: `uv run pytest tests/unit/test_market_ingestion.py` (7 passed), full non-integration
  suite (428 passed, 100 deselected — integration/e2e need Docker, which is up but wasn't
  re-run in full this slice), ruff + pyright clean on every touched file. `graphify update .`
  run after the code change.
- **Not yet committed** — this and the wallet-activity/entity-graph slice below are both still
  sitting uncommitted in the working tree; nothing has been committed this session.

**Immediate next actions:** decide whether to commit (nothing committed yet — ask the user, don't
commit unilaterally per repo convention). Longer-lived gap to flag to the user: the ingestion job
only has ~17 hours of real history right now, not the 30-day backtest window Phase 5 implicitly
assumed — worth deciding if/when to reset the cursor to backfill.

## Research job consumer wired up (2026-09-16, later the same day)

Closed the gap flagged above: `research_routes.py` (Codex, previous slice) let an Admin enqueue a
RESEARCH job via `POST /api/research/jobs`, but nothing ever consumed it -- `apps/research_worker`
did nothing but heartbeat. User decision (asked explicitly): the consumer re-runs the backtest an
existing `ExperimentRecord` describes and saves the result as a new record.

- **Network isolation constraint found and resolved per user decision**: `BacktestOrchestrator`
  normally resolves the traded `Instrument` (including price/quantity precision) via a live
  `discover_instruments()` call -- but `research`'s Docker network is `internal: true` (Fase 7
  isolation, PENDING.md), so it can never reach Kraken. Fix: `ExperimentRecord` now stores the
  full `Instrument` identity (`instrument_market_type`/`price_increment`/`quantity_increment`/
  `min_quantity`, migration `0023_experiment_precision` -- kept to 26 chars, the same
  varchar(32) `alembic_version` gotcha 0019 already documents) so a re-run reconstructs it
  offline instead of calling a live adapter. `BacktestOrchestrator.run()` now accepts an optional
  pre-resolved `Instrument` to skip discovery entirely (backward compatible: the live
  `POST /api/backtests` route passes none, unchanged behavior).
- New `wallybot/application/research_runner.py`: claims one RESEARCH job, looks up its
  `ExperimentRecord`, re-runs the backtest offline, saves the new record, and always reaches
  `complete` or `fail` on the job (never leaves it RUNNING). Wired into
  `wallybot/infrastructure/jobs.py`'s `tick()` for `service == "research"` -- **as a lazy/local
  import**, not module-level: `research_runner` pulls in `duckdb` via `backtest_orchestrator`,
  which only exists in the `runtime-research` image (api/research), not the base image
  worker/scheduler run on. A module-level import crashed both of those on redeploy (caught and
  fixed this slice, see below).
- Added a `fail()` transition to `wallybot/domain/research_job.py` and a matching
  `ResearchJobRepository.fail()` -- neither existed before; a job that couldn't complete had no
  defined way to stop being RUNNING.
- `research`'s Docker network never had the `historical_data` volume mounted (added, read-only)
  and `ProcessSettings` (worker/scheduler/research's settings, distinct from the api-only
  `Settings`) never had `historical_data_root` (added).
- Migration 0023 also grants `wally_research` `USAGE`/`SELECT` on `experiment_records_id_seq` --
  it had SELECT/INSERT on the table since migration 0015 but never the sequence, so it could
  never actually have inserted a row even before this slice (same gap 0017 already found and
  fixed for `wally_api`).

**Bugs found and fixed while verifying this end-to-end against the live Docker stack** (not just
unit tests -- this repo's own convention, see the 0018/0019 grant gotchas):
1. Migration revision id `0023_experiment_instrument_precision` (36 chars) exceeded
   `alembic_version.version_num`'s varchar(32) and failed `alembic upgrade head` with
   `StringDataRightTruncation` -- renamed to `0023_experiment_precision` (both the revision id
   and the file).
2. `jobs.py` importing `research_runner` at module level crashed `worker`/`scheduler` on startup
   (`ModuleNotFoundError: No module named 'duckdb'` -- those run the base image, not
   `runtime-research`). Fixed with a local import inside the `service == "research"` branch.
3. The pre-fsync-fix corrupted run (documented earlier in this file) left not just 60 zero-byte
   `.parquet` files (already cleaned) but 62 sibling zero-byte `.manifest.json` files that were
   never cleaned -- `json.loads("")` on one of them broke every `read_candles` call. Found via a
   real end-to-end smoke test (seeded a real `ExperimentRecord` + `JobRow` in the live DB,
   watched `research_worker` claim and fail it, read the actual error), cleaned up, re-verified:
   `research_worker` claimed a fresh job, re-ran the backtest from real local Parquet data with
   zero network access, saved a new `ExperimentRecord`, marked the job COMPLETED. Smoke-test rows
   deleted afterward.

Verified: full suite 557 passed (444 unit/property + 113 integration, up from 105 -- new
`test_research_runner.py` plus updated `test_experiment.py`/`test_backtest_orchestrator.py`/
`test_research_job.py`/`test_jobs.py`/`test_experiment_persistence.py` for the new
`ExperimentRecord` fields and `tick()` signature). Ruff/pyright clean (same one pre-existing
unrelated `auth_routes.py` error confirmed present on `master` before any of this session's
changes). All four backend services (api/worker/scheduler/research) rebuilt, redeployed, healthy.

**Not yet committed** — this slice, on top of everything else already described in this file,
still sits uncommitted. Still true: never commit without the user asking first.

**This session's delivery:** connected the last two Phase 10 OBSERVE-only signals that were not
yet surfaced in the UI — wallet activity (on-chain feed) and the Entity Correlation Graph. Same
end-to-end pattern as Smart Money/whale flow/token risk/provider reliability/price consensus:

- `wallybot/infrastructure/wallet_activity_repository.py`: `list_recent(limit=100)` — newest-first
  across every monitored wallet (previously only had `list_for_wallet`, per-wallet).
- `wallybot/infrastructure/relationship_repository.py`: `list_recent(limit=100)` — newest-first
  across the whole graph (previously only had `find_by_node`, node-scoped traversal).
- `GET /api/intelligence/wallet-activity` and `GET /api/intelligence/entity-graph` in
  `apps/api/intelligence_routes.py` + `apps/api/dto.py`'s `WalletActivityRowView`/
  `WalletActivityView`, `RelationshipRowView`/`EntityGraphView`.
- **Same recurring access-control gap found again** (5th time: 0012/0013/0016/0017/now):
  `wally_api` had no grant on `wallet_activity_events`/`relationships` — migration
  `0018_wallet_relationship_grants` (had to keep the revision id ≤32 chars — Postgres's
  `alembic_version.version_num` column caps at varchar(32); a first, longer id caused
  `StringDataRightTruncation` on `alembic upgrade head`, now known for next time). Bumped
  `apps/api/main.py`'s hardcoded Alembic revision check to
  `"0018_wallet_relationship_grants"` (same recurring rough edge, still not dynamic).
- Frontend: `apps/web/src/lib/dto.ts`'s `walletActivityRowSchema`/`walletActivitySchema`,
  `relationshipRowSchema`/`entityGraphSchema`; `useWalletActivityData.ts`/`useEntityGraphData.ts`;
  `WalletActivitySection.tsx`/`EntityGraphSection.tsx` composed into `IntelligencePage.tsx`
  (no new nav entry needed — same "Inteligencia" page as the other five signals) and wired into
  `Dashboard.tsx`. English strings added to `lib/locales/en.json`.
- Tests: `tests/integration/test_wallet_activity_route.py` + `test_entity_graph_route.py`
  (auth-required + seeded/empty via the real repositories); a new Playwright test in
  `observability.spec.ts` (populated + empty states) plus the two new endpoints added to the
  shared `shell()` fixture's route map (every test that opens `/intelligence` now needs them
  stubbed, since `Dashboard.tsx` fires both hooks unconditionally on that page).

**Verified:** full suite 516 passed (510→516), ruff/pyright clean on every touched file, domain
purity untouched (no domain changes this slice — pure repository/API/frontend wiring), `tsc`/
`eslint`/`next build` clean, full Playwright suite green (9 passed, 1 skipped as always) including
the new wallet-activity/entity-graph test. Rebuilt **both** the `api`-research image and the base
`wallybot-api:0.1.0` image (the `migrate`/`worker`/`scheduler` services share the base image via
docker-compose's `&app` anchor — rebuilding only `api`/`web` is not enough when a new migration
ships; learned this the hard way this session after `migrate` silently ran against a stale image
with no `0018` file present). Migration applied via `docker compose up migrate`, `api` restarted,
`gateway`/`api`/`web` all healthy, `/health/ready` → `{"status":"ready"}` at
`0018_wallet_relationship_grants`, `/login` serving 200 through the gateway. Not yet committed.

**Phase 10 status: now fully surfaced in the UI** — all 5 OBSERVE-only signal families
(Smart Money, whale flow, token risk, provider reliability/price consensus, wallet activity,
entity graph) are visible on the Inteligencia page. Remaining Phase 10 gap: Slice 4b (real
wallet/entity vendor adapter — blocked on an API key decision, per `.ai/HANDOFF.md`).

**What's realistically left for a "finished product"** (unchanged from before this slice, see
`.ai/HANDOFF.md`'s longer list): the Parquet dataset-ingestion job so `POST /api/backtests`
returns non-empty results in production; Phase 12 Slice 4 (real AI adapter, needs an authorized
model/API key decision) + a scheduler actually calling `ShadowDecisionService`; Phases 7/8
(research agents, Telegram); Phase 9 (LIVE trading, gated behind RISK.md/SECURITY.md evidence).

**Immediate next actions:** commit this slice's changes (not yet committed). Then, per
`docs/PENDING.md`'s delivery order, the next body of work is either the Parquet ingestion job
(makes backtests non-empty in production) or Phase 6/12 Slice 4 (needs a model/API key decision
from the user first — cannot proceed on that path without one).


## System service summary — 2026-09-15

Codex added counts for reported essential connections/processes, healthy services and services needing review. Optional integrations excluded; failed refresh labels the summary as the last successful check. ES/EN and responsive layout preserved. Focused mocked browser test passed (counts, stale refresh, empty processes, mobile); screenshot inspected; ESLint, TypeScript and targeted Ruff passed. Docker unavailable (named pipe missing), so production-stack verification and web deployment were not performed. New apps/web/playwright.ui.config.ts runs only fully intercepted observability specs using scripts/ui_test_server.py, stripping WALLY_* environment and directing fallback API traffic to an unused local port. No backend changes.

Final verification: all 8 mocked observability browser tests passed with the frontend-only config; Graphify AST update completed; git diff --check clean. Docker deployment remains pending.


## Backtest form clarity — 2026-09-15

Codex UI: allocation now explicitly a fraction, with examples for allocation/fees/slippage. Dates disclose browser time zone and UTC transport; invalid or reversed/equal windows are blocked before API submission with translated accessible errors. Instrument names are required with max length 16; feature window required, 1–500 per API. Decimal strings remain unchanged in requests. Focused browser test passed for rejected dates without POST, ES/EN errors, decimal payloads, successful execution/history and server 422. ESLint/TypeScript passed. No backend or deployment changes; previous Docker availability limitation remains.
