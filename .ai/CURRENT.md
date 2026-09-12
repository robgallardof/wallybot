# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 (authenticated foundation) is done; Phase 2 is
"Fake/Kraken market discovery, data quality, streaming, features and scanner" — a multi-slice scope
tracked in `docs/PHASE_2.md` (mirrors `docs/PHASE_1.md`'s ordered-slice format).

**Status: Slices 1-4 done and verified** (market domain model + seeded `FakeExchange`; instrument
universe filters; data quality gate; Redis hot-tier caching). Slices 5-9 (Parquet history, real
Kraken adapter, streaming, features, scanner) are a documented backlog only — not started, not
scaffolded as empty placeholders (per `ARCHITECTURE.md`'s "create modules when a real capability
needs them" rule).

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration, wired `next-themes`, fixed a stale-nginx-CSP-header
   bug and a missing `nonce` prop on next-themes' injected script — see `.ai/DECISIONS.md`.
2. Initialized `.git` (previously absent) as an explicit safety checkpoint (commit `b15a0dc`)
   before a requested repo-wide refactor.
3. Refactor: explicit backend response DTOs + cookie-helper DRY fix, frontend `lib/api.ts` split
   into `lib/dto.ts`/`lib/api-client.ts`, `Dashboard.tsx`/`Auth.tsx` split into hooks + focused
   components (commit `7e16332`). Deliberately left `AuthService`/`crypto`/`throttle`/
   `domain/control.py` untouched — already SRP-cohesive, no concrete defect to fix.
4. Phase 2 Slice 1 (commit `2d75de8`): `wallybot/domain/{clock,market}.py` (pure domain: `Clock`
   protocol, `Instrument`, `Candle`, `MarketDataProvider` protocol), `wallybot/exchanges/fake.py`
   (`FakeExchange`), `tests/contract/` (new test layer), `tests/unit/test_market_domain.py`.
5. Phase 2 Slice 2 (commit `fa2125b`): `MarketSnapshot` + `fetch_snapshot` on the port,
   `wallybot/market/universe.py` (`UniverseFilterConfig`, `evaluate_universe`), extended
   `FakeExchange` + contract suite, `tests/unit/test_universe.py`.
6. Phase 2 Slice 3 (commit `40bf7f1`): `wallybot/data/quality.py` — stateful cross-candle quality
   gate (`QualityStatus`/`QualityPolicy`/`evaluate_series_quality`, 7 blocking + 2 warning-only
   reason codes per DATA.md). Extracted `TIMEFRAME_DURATIONS` into `domain/market.py` (DRY). Also
   fixed a real `.gitignore` bug: a bare `data/` entry was silently excluding the new
   `wallybot/data/` package from every `git status`/`add` — scoped to `/data/` (root only).
7. Phase 2 Slice 4 (not yet committed): `wallybot/infrastructure/market_cache.py` — `MarketCache`
   (Redis-backed hot tier for snapshots, ADR-003) typed against a narrow `RedisLike` Protocol
   (not the concrete `redis.asyncio.Redis` class, so tests don't need a real client). Deliberately
   has no "is this fresh" method — per ADR-003, cache expiry never implies valid fresh data; it
   just stores/returns exactly what it was given. `tests/integration/test_market_cache.py` (real
   Redis via testcontainers, reusing the existing `dependencies` fixture) — including the key test
   that a stale-but-unexpired snapshot comes back with its stale timestamp unchanged.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 61
passed. `uv run ruff check` and `uv run pyright` on all new files → clean. Domain purity confirmed
(zero FastAPI/SQLAlchemy/CCXT imports in `wallybot/domain/`, `wallybot/market/`, `wallybot/data/`).

**Branch:** `master`. Commits so far: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
this session's Slice 4 commit (not yet made — do that before considering this task closed).

**Immediate next actions:** Confirm with the user before starting Phase 2 Slice 5 (historical
Parquet writer + manifest, ADR-005) — `docs/PHASE_2.md` has the full ordered backlog if they just
say "keep going." Slice 5 needs a filesystem-writing adapter (checksummed, atomic-publish
partitions) — no existing pattern for that in this repo yet, worth designing carefully rather than
copying an existing file.
