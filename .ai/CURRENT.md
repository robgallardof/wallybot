# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 (authenticated foundation) is done; Phase 2 is
"Fake/Kraken market discovery, data quality, streaming, features and scanner" — a multi-slice scope
tracked in `docs/PHASE_2.md` (mirrors `docs/PHASE_1.md`'s ordered-slice format).

**Status: Slices 1-2 done and verified** (market domain model + seeded `FakeExchange`; instrument
universe filters). Slices 3-9 (data quality gate, Redis caching, Parquet history, real Kraken
adapter, streaming, features, scanner) are a documented backlog only — not started, not scaffolded
as empty placeholders (per `ARCHITECTURE.md`'s "create modules when a real capability needs them"
rule).

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration (`apps/web` scripts were still calling uninstalled
   `vite`), wired `next-themes`, fixed a stale-nginx-CSP-header bug and a missing `nonce` prop on
   next-themes' injected script — see `.ai/DECISIONS.md` for both root causes.
2. Initialized `.git` (previously absent) as an explicit safety checkpoint (commit `b15a0dc`)
   before a requested repo-wide refactor.
3. Refactor: explicit backend response DTOs (`apps/api/dto.py`) + cookie-helper DRY fix, frontend
   `lib/api.ts` split into `lib/dto.ts`/`lib/api-client.ts`, `Dashboard.tsx`/`Auth.tsx` split into
   hooks + focused components (commit `7e16332`). Deliberately left `AuthService`/`crypto`/
   `throttle`/`domain/control.py` untouched — already SRP-cohesive, no concrete defect to fix.
4. Phase 2 Slice 1 (commit `2d75de8`): `wallybot/domain/{clock,market}.py` (pure domain: `Clock`
   protocol, `Instrument`, `Candle`, `MarketDataProvider` protocol), `wallybot/exchanges/fake.py`
   (`FakeExchange`, seeded/deterministic/network-free), `tests/contract/` (new test layer: shared
   `MarketDataProvider` contract suite, run against `FakeExchange`), `tests/unit/test_market_domain.py`.
5. Phase 2 Slice 2 (not yet committed): added `MarketSnapshot` + `fetch_snapshot` to the
   `MarketDataProvider` port (needed for spread filtering), `wallybot/market/universe.py`
   (`UniverseFilterConfig`, `evaluate_instrument`/`evaluate_universe`, `eligible_instruments`),
   extended `FakeExchange` + the contract suite, added `tests/unit/test_universe.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 44
passed. `uv run ruff check` and `uv run pyright` on all new files → clean. Domain purity confirmed
(zero FastAPI/SQLAlchemy/CCXT imports in `wallybot/domain/` and `wallybot/market/`).

**Branch:** `master`. Commits so far: `b15a0dc` (pre-refactor safety snapshot) → `7e16332` (DTO/SRP
refactor) → `2d75de8` (Phase 2 Slice 1) → this session's Slice 2 commit (not yet made — do that
before considering this task closed).

**Immediate next actions:** Confirm with the user before starting Phase 2 Slice 3 (data quality
gate: PASS/WARNING/FAILURE with reason codes across a candle series) — `docs/PHASE_2.md` has the
full ordered backlog if they just say "keep going."
