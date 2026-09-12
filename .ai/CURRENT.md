# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 is done; Phase 2 is "Fake/Kraken market
discovery, data quality, streaming, features and scanner" — tracked in `docs/PHASE_2.md`.

**Status: Slices 1-5, 8 and 9 done and verified.** Only Slices 6 (real Kraken adapter) and 7
(streaming) remain, and both are **explicitly blocked** on real Kraken network access/credentials
this session doesn't have — not skipped by oversight. Every other Phase 2 capability the backlog
named (discovery, universe filtering, data quality, Redis caching, historical storage, features,
scanning) exists and is tested. **Before touching 6/7, ask the user for Kraken sandbox/API access.**

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration, `next-themes`, a stale-nginx-CSP-header bug, a
   missing `nonce` prop on next-themes' injected script.
2. Initialized `.git` (previously absent) as a safety checkpoint (commit `b15a0dc`).
3. Refactor: backend response DTOs, cookie-helper DRY fix, frontend `lib/api.ts`/`Dashboard.tsx`/
   `Auth.tsx` split into hooks + focused components (commit `7e16332`).
4. Phase 2 Slice 1 (`2d75de8`): `wallybot/domain/{clock,market}.py`, `wallybot/exchanges/fake.py`.
5. Phase 2 Slice 2 (`fa2125b`): `MarketSnapshot`, `wallybot/market/universe.py`.
6. Phase 2 Slice 3 (`40bf7f1`): `wallybot/data/quality.py`. Fixed a `.gitignore` bug.
7. Phase 2 Slice 4 (`4f62804`): `wallybot/infrastructure/market_cache.py` (Redis hot tier).
8. Phase 2 Slice 5 (`c0567ae`): `wallybot/data/historical.py` (Parquet writer). Added `pyarrow`,
   caught and fixed a real CVE (`pip-audit`) before committing.
9. Phase 2 Slice 8 (`1bf0b3d`, taken out of order — see status note): `wallybot/domain/features.py`
   (`FeatureVector`, `LookaheadError`, `FeatureEngine` protocol), `wallybot/features/simple.py`
   (`SimpleFeatureEngine` — plain-Python SMA/momentum).
10. Phase 2 Slice 9 (not yet committed): `wallybot/scoring/simple.py` (`Score`, `score_momentum`
    — deterministic, versioned) and `wallybot/application/scanner.py` (`scan_universe` — the
    first use case composing multiple capability packages: filters the universe, scores every
    eligible instrument, ranks, returns top `max_finalists` + rejected IDs). Both are packages
    explicitly named in `ARCHITECTURE.md`'s planned layout. `tests/unit/{test_scoring,
    test_scanner}.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 81
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed for
`wallybot/domain/` throughout.

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → this session's Slice 9 commit (not yet made — do that before
considering this task closed).

**Immediate next actions:** Phase 2's non-Kraken-dependent backlog is complete. Ask the user: (a)
do they have Kraken sandbox/API credentials to unblock Slices 6-7, or (b) do they want to move on
to Phase 3 (scoring, regimes, strategies, allocation, deterministic risk) per `ARCHITECTURE.md`'s
implementation sequence, which — like Slices 1/2/8/9 — can be built and tested against
`FakeExchange` without needing real Kraken access at all.
