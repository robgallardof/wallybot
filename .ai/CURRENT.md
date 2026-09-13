# Current task

**Task:** Phase 3 ("Scoring, regimes, strategies, allocation and tested deterministic risk" per
`ARCHITECTURE.md`'s implementation sequence) is now **complete** — all 5 slices delivered and
verified, tracked in `docs/PHASE_3.md`. User has explicitly said to keep going without stopping to
check in between slices for the rest of this session.

**Phase 2 status: complete except Slice 7 (streaming)**, deferred pending the ADR-004
WebSocket-vs-CCXT-Pro benchmark.

**Phase 3 status: complete (Slices 1-5).** `RiskEngine` (Slice 5) was scoped tightly to exactly
what RISK.md's own Invariants/Initial-Policy/Approval-contract sections specify — nothing invented,
every gap (volatility/correlation, AI checks, reconciliation/breaker *mechanism*, cluster
concentration, emergency-operations actions) documented explicitly in the module docstrings and
`docs/PHASE_3.md`, not silently missing.

**Delivered this session (chronological, latest last):**
- Fixed the Vite→Next.js migration, DTO/SRP refactor (commits `b15a0dc`, `7e16332`).
- Phase 2 Slices 1-6, 8, 9 (commits `2d75de8` → `e0eb7f5`) — see `docs/PHASE_2.md`.
- **Correction logged in `.ai/DECISIONS.md`:** wrongly assumed Kraken's adapter needed
  credentials; its market-data endpoints are public.
- Phase 3 Slices 1-4 (commits `fde858c`, `a04207e`, `56883af`, `b5710a9`) — see `docs/PHASE_3.md`.
- Phase 3 Slice 5 (not yet committed): `wallybot/domain/risk.py` (`RiskDecision`,
  `ExchangeStatus`, `RiskPolicy`, `RiskContext`, `RiskAssessment`, `RiskEngine` protocol) and
  `wallybot/risk/deterministic_risk_engine.py` (`DeterministicRiskEngine`).
  `tests/unit/{test_risk,test_deterministic_risk_engine}.py`,
  `tests/property/test_risk_invariants.py` (Hypothesis).
- **Architecture bug found and fixed mid-slice:** `domain/risk.py` initially imported from
  `wallybot/data/quality.py` (a capability package) — backwards for the innermost domain layer.
  Extracted `QualityStatus`/`QualityIssue`/`QualityReport` into new `wallybot/domain/quality.py`;
  `data/quality.py` now imports them back and still re-exports them for existing callers. Logged
  in `.ai/DECISIONS.md` with the exact check to run before adding any future `domain/*.py` import.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 168
passed. `uv run ruff check`, `uv run pyright` → clean. Confirmed via `grep` that zero files under
`wallybot/domain/` import from any capability package (`data`, `exchanges`, `market`, `scoring`,
`application`, `signals`, `strategies`, `portfolio`, `infrastructure`).

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → `e0eb7f5` → `fde858c` → `a04207e` → `56883af` →
`b5710a9` → this session's Slice 5 commit (not yet made — do that before considering this task
closed).

**Immediate next actions:** Phase 3 is done. Per `ARCHITECTURE.md`'s implementation sequence,
Phase 4 is next: "Replay, paper execution, ledger and recovery under failures" — the first phase
needing real persistence (order intents, fills, ledger postings, position projections) beyond
anything built in Phases 2-3, which were all pure domain/capability code plus one Redis cache and
one filesystem writer. This is a substantial jump in infrastructure surface (new DB tables/
migrations, transactional outbox, reconciliation) — worth a fresh backlog-and-first-slice plan
the same way Phase 2 and Phase 3 each started, not assumed to follow the exact same slice shape.
