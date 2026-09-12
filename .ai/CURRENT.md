# Current task

**Task:** Phase 2 kickoff — "el propósito de la aplicación... fases del mercado." Per
`ARCHITECTURE.md`'s implementation sequence, Phase 1 is done; Phase 2 is "Fake/Kraken market
discovery, data quality, streaming, features and scanner" — tracked in `docs/PHASE_2.md`.

**Status: Slices 1-6, 8 and 9 done and verified. Only Slice 7 (streaming) remains.** It needs the
native-Kraken-WebSocket-vs-CCXT-Pro benchmark ADR-004 explicitly defers — a materially larger,
different piece of work, not something to fold into a quick continuation.

**Important correction made this session:** Slice 6 was initially assumed blocked on the user
providing Kraken API credentials. That was **wrong** — the user pushed back, prompting an actual
check: Kraken's market-data endpoints (AssetPairs/OHLC/Ticker) are public/unauthenticated; only
trading/balance endpoints need a key, and those are Phase 4's problem, not this one. This session
has real outbound network access, verified directly against the live API. See `.ai/DECISIONS.md`.

**Delivered this session (in order):**
1. Fixed the Vite→Next.js frontend migration, `next-themes`, a stale-nginx-CSP-header bug.
2. Initialized `.git` as a safety checkpoint (commit `b15a0dc`).
3. Refactor: backend response DTOs, cookie-helper DRY fix, frontend hooks/component split
   (commit `7e16332`).
4. Phase 2 Slice 1 (`2d75de8`): market domain model, `FakeExchange`.
5. Phase 2 Slice 2 (`fa2125b`): `MarketSnapshot`, `wallybot/market/universe.py`.
6. Phase 2 Slice 3 (`40bf7f1`): `wallybot/data/quality.py`. Fixed a `.gitignore` bug.
7. Phase 2 Slice 4 (`4f62804`): `wallybot/infrastructure/market_cache.py` (Redis hot tier).
8. Phase 2 Slice 5 (`c0567ae`): `wallybot/data/historical.py` (Parquet writer). Added `pyarrow`,
   fixed a real CVE via `pip-audit` before committing.
9. Phase 2 Slice 8 (`1bf0b3d`, taken out of order): `wallybot/domain/features.py`,
   `wallybot/features/simple.py` (`SimpleFeatureEngine`).
10. Phase 2 Slice 9 (`853cb4b`): `wallybot/scoring/simple.py`, `wallybot/application/scanner.py`
    (`scan_universe`).
11. Phase 2 Slice 6 (not yet committed): `wallybot/exchanges/kraken.py` (`KrakenExchange`) —
    real Kraken adapter via public REST endpoints only, no credentials. `KrakenTransport` Protocol
    for testability (mirrors `MarketCache`'s `RedisLike`). `tests/contract/test_kraken_exchange.py`
    replays real captured Kraken responses (no live network in the test run, per TESTING.md).
    Also manually verified the real production path live against the actual Kraken API. Moved
    the shared `FixedClock` test double into `market_data_provider_suite.py` (DRY).

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 88
passed. `uv run ruff check`, `uv run pyright` → clean.

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → this session's Slice 6 commit (not yet made — do
that before considering this task closed).

**Immediate next actions:** Ask the user whether to attempt Slice 7 (streaming — needs the
ADR-004 WebSocket-vs-CCXT-Pro benchmark, real sustained network access, and materially more design
work than any slice so far) or move on to Phase 3 (scoring, regimes, strategies, allocation,
deterministic risk) per `ARCHITECTURE.md`'s implementation sequence.
