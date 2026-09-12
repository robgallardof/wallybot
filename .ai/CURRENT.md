# Current task

**Task:** Continuing past Phase 2 into Phase 3 ("Scoring, regimes, strategies, allocation and
tested deterministic risk" per `ARCHITECTURE.md`'s implementation sequence), tracked in
`docs/PHASE_3.md` (same ordered-slice format as Phase 1/2).

**Phase 2 status: complete except Slice 7 (streaming)**, deferred pending the ADR-004
WebSocket-vs-CCXT-Pro benchmark — a materially different, larger piece of work.

**Phase 3 status: Slice 1 (regime classification) done and verified.** Slices 2-5 are a documented
backlog only. **Slice 5 (`RiskEngine`) is explicitly flagged to get its own dedicated planning
session** — `RISK.md` is extraordinarily detailed and says "do not invent universally safe market
thresholds"; it must not be rushed into the same pass as lower-stakes work.

**Delivered this session (chronological, latest last):**
- Fixed the Vite→Next.js migration, DTO/SRP refactor (commits `b15a0dc`, `7e16332`).
- Phase 2 Slices 1-6, 8, 9 (commits `2d75de8`, `fa2125b`, `40bf7f1`, `4f62804`, `c0567ae`,
  `1bf0b3d`, `853cb4b`, `e0eb7f5`) — see `docs/PHASE_2.md` for full detail per slice.
- **Correction logged in `.ai/DECISIONS.md`:** initially assumed the Kraken adapter (Slice 6)
  needed user-provided credentials; wrong — Kraken's market-data endpoints are public. Verify a
  third-party API's actual auth requirements before reporting something as blocked on credentials.
- Phase 3 Slice 1 (not yet committed): `wallybot/domain/regime.py` (`Regime`,
  `RegimeClassification`, `classify_regime` — deterministic, versioned, reads Slice 8's
  `momentum_<window>` feature). `tests/unit/test_regime.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 95
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed.

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → `e0eb7f5` → this session's Phase 3 Slice 1 commit
(not yet made — do that before considering this task closed).

**Immediate next actions:** Confirm with the user before Phase 3 Slice 2 (`Strategy` port + one
deterministic strategy producing a `StrategySignal` from a `RegimeClassification` + `FeatureVector`
+ scanner finalist — still no money math, still buildable/testable against `FakeExchange` data
alone). Do not attempt Slice 4 (`PortfolioAllocator`) or Slice 5 (`RiskEngine`) without an explicit
dedicated check-in first — both touch `RISK.md`'s stated ceilings and sizing formula, the most
safety-critical part of this entire system.
