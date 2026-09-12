# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 (authenticated foundation) is done; Phase 2 is
"Fake/Kraken market discovery, data quality, streaming, features and scanner" — a multi-slice scope
tracked in `docs/PHASE_2.md` (mirrors `docs/PHASE_1.md`'s ordered-slice format).

**Status: Slices 1-5 and 8 done and verified** (market domain model + `FakeExchange`; universe
filters; data quality gate; Redis hot-tier caching; historical Parquet writer; feature engine).
**Slices 6 and 7 are explicitly blocked**, not skipped by oversight: 6 (real Kraken adapter) and 7
(streaming) need real Kraken network access/credentials this session doesn't have — ask the user
for those before attempting either. Slice 9 (the scanner) is next since it only needs
`FakeExchange`, matching the pattern every slice so far has used except Slice 4 (Redis) and 5
(filesystem).

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration, wired `next-themes`, fixed a stale-nginx-CSP-header
   bug and a missing `nonce` prop on next-themes' injected script.
2. Initialized `.git` (previously absent) as a safety checkpoint (commit `b15a0dc`).
3. Refactor: explicit backend response DTOs + cookie-helper DRY fix, frontend `lib/api.ts` split,
   `Dashboard.tsx`/`Auth.tsx` split into hooks + focused components (commit `7e16332`).
4. Phase 2 Slice 1 (`2d75de8`): `wallybot/domain/{clock,market}.py`, `wallybot/exchanges/fake.py`.
5. Phase 2 Slice 2 (`fa2125b`): `MarketSnapshot` + `fetch_snapshot`, `wallybot/market/universe.py`.
6. Phase 2 Slice 3 (`40bf7f1`): `wallybot/data/quality.py`. Fixed a `.gitignore` bug (`data/` was
   silently excluding `wallybot/data/`).
7. Phase 2 Slice 4 (`4f62804`): `wallybot/infrastructure/market_cache.py` (Redis hot tier).
8. Phase 2 Slice 5 (`c0567ae`): `wallybot/data/historical.py` (checksummed atomic Parquet writer).
   Added `pyarrow` dependency — caught and fixed a real CVE in the first resolved version
   (`pip-audit`) before committing.
9. Phase 2 Slice 8 (not yet committed, taken out of order — see status note above):
   `wallybot/domain/features.py` (`FeatureVector`, `LookaheadError`, `FeatureEngine` protocol) and
   `wallybot/features/simple.py` (`SimpleFeatureEngine` — plain-Python SMA/momentum, no NumPy/
   Pandas). Every candle is checked against `as_of`; one closing later raises `LookaheadError`.
   `tests/unit/test_features.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 75
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed for
`wallybot/domain/` (zero framework imports across all domain modules).

**Branch:** `master`. Commits so far: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → this session's Slice 8 commit (not yet made — do that before considering
this task closed).

**Immediate next actions:** Confirm with the user before starting Phase 2 Slice 9 (the scanner —
universe ranking, finalist selection, per `docs/PHASE_2.md`). It composes Slice 2's universe filter
with Slice 8's feature engine, so both need to already exist — they do now. After Slice 9, Phase 2's
backlog is only 6 and 7 left, both blocked on the same missing Kraken access.
