# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 (authenticated foundation) is done; Phase 2 is
"Fake/Kraken market discovery, data quality, streaming, features and scanner" — a multi-slice scope
tracked in `docs/PHASE_2.md` (mirrors `docs/PHASE_1.md`'s ordered-slice format).

**Status: Slices 1-5 done and verified** (market domain model + seeded `FakeExchange`; instrument
universe filters; data quality gate; Redis hot-tier caching; historical Parquet writer). Slices 6-9
(real Kraken adapter, streaming, features, scanner) are a documented backlog only — not started.

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration, wired `next-themes`, fixed a stale-nginx-CSP-header
   bug and a missing `nonce` prop on next-themes' injected script — see `.ai/DECISIONS.md`.
2. Initialized `.git` (previously absent) as a safety checkpoint (commit `b15a0dc`) before a
   requested repo-wide refactor.
3. Refactor: explicit backend response DTOs + cookie-helper DRY fix, frontend `lib/api.ts` split,
   `Dashboard.tsx`/`Auth.tsx` split into hooks + focused components (commit `7e16332`).
4. Phase 2 Slice 1 (`2d75de8`): `wallybot/domain/{clock,market}.py`, `wallybot/exchanges/fake.py`
   (`FakeExchange`), `tests/contract/` (new test layer), `tests/unit/test_market_domain.py`.
5. Phase 2 Slice 2 (`fa2125b`): `MarketSnapshot` + `fetch_snapshot`, `wallybot/market/universe.py`,
   `tests/unit/test_universe.py`.
6. Phase 2 Slice 3 (`40bf7f1`): `wallybot/data/quality.py` (stateful cross-candle quality gate).
   Fixed a `.gitignore` bug (`data/` was silently excluding `wallybot/data/`).
7. Phase 2 Slice 4 (`4f62804`): `wallybot/infrastructure/market_cache.py` (`MarketCache`, Redis
   hot tier for snapshots, ADR-003 — never claims freshness).
8. Phase 2 Slice 5 (not yet committed): added `pyarrow` dependency (user chose it over polars/
   deferring via AskUserQuestion) — caught and fixed a real CVE in the first resolved version
   before committing, see `.ai/DECISIONS.md`. Added `wallybot/domain/id_generator.py`
   (`IdGenerator` protocol) and `wallybot/data/historical.py` (`HistoricalStore`,
   `PartitionManifest`) — checksummed, atomically-published Parquet partitions with a sidecar
   manifest, per ADR-005/DATA.md. OHLCV columns use `pyarrow.decimal128(18, 8)`, not float.
   `tests/unit/test_historical.py` (uses `tmp_path`, no Docker needed).

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 68
passed. `uv run ruff check`, `uv run pyright`, `uv run pip-audit` on all new files/dependencies →
all clean. Domain purity confirmed for `wallybot/domain/` (zero framework imports).

**Branch:** `master`. Commits so far: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → this session's Slice 5 commit (not yet made — do that before considering this task
closed).

**Immediate next actions:** Confirm with the user before starting Phase 2 Slice 6 (real Kraken
adapter via CCXT, passing the same contract suite `FakeExchange` already passes) — `docs/PHASE_2.md`
has the full ordered backlog if they just say "keep going." Slice 6 will need real (or sandbox)
Kraken credentials/network access to test against, unlike every slice so far which needed only
`FakeExchange`, testcontainers, or `tmp_path` — worth flagging that dependency explicitly before
starting.
