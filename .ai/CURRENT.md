# Current task

**Task:** Continuing past Phase 2 into Phase 3 ("Scoring, regimes, strategies, allocation and
tested deterministic risk" per `ARCHITECTURE.md`'s implementation sequence), tracked in
`docs/PHASE_3.md` (same ordered-slice format as Phase 1/2). User has explicitly said to keep going
without stopping to check in between slices for the rest of this session.

**Phase 2 status: complete except Slice 7 (streaming)**, deferred pending the ADR-004
WebSocket-vs-CCXT-Pro benchmark — a materially different, larger piece of work.

**Phase 3 status: Slices 1-4 done and verified** (regime classification; `Strategy` port +
`TrendFollowingStrategy`; `SignalAggregator`; `PortfolioAllocator`). **Only Slice 5 (`RiskEngine`)
remains**, and it stays a documented backlog item requiring extra care — `RISK.md` is
extraordinarily detailed and says "do not invent universally safe market thresholds." Building it
means implementing RISK.md's own given values/rules exactly, with property-test coverage per
TESTING.md's ≥95% branch-coverage target for risk/accounting, not inventing anything new.

**Delivered this session (chronological, latest last):**
- Fixed the Vite→Next.js migration, DTO/SRP refactor (commits `b15a0dc`, `7e16332`).
- Phase 2 Slices 1-6, 8, 9 (commits `2d75de8`, `fa2125b`, `40bf7f1`, `4f62804`, `c0567ae`,
  `1bf0b3d`, `853cb4b`, `e0eb7f5`) — see `docs/PHASE_2.md` for full detail per slice.
- **Correction logged in `.ai/DECISIONS.md`:** initially assumed the Kraken adapter (Slice 6)
  needed user-provided credentials; wrong — Kraken's market-data endpoints are public. Verify a
  third-party API's actual auth requirements before reporting something as blocked on credentials.
- Phase 3 Slice 1 (`fde858c`): `wallybot/domain/regime.py`.
- Phase 3 Slice 2 (`a04207e`): `wallybot/domain/strategy.py`, `wallybot/strategies/trend_following.py`.
- Phase 3 Slice 3 (`56883af`): `wallybot/domain/aggregation.py`, `wallybot/signals/weighted_aggregator.py`.
- Phase 3 Slice 4 (not yet committed): `wallybot/domain/portfolio.py` (`Bucket`, `PortfolioPolicy`
  — every default taken directly from RISK.md's Initial Policy table, none invented —
  `PortfolioState`, `AllocationProposal`, `PortfolioAllocator` protocol) and
  `wallybot/portfolio/simple_allocator.py` (`SimplePortfolioAllocator` — bucket-headroom sizing
  scaled by confidence, capped by speculative operating/single-asset ceilings, never reaching the
  absolute ceiling; raises on SELL since position data doesn't exist yet).
  `tests/unit/{test_portfolio,test_simple_allocator}.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 140
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed throughout.

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → `e0eb7f5` → `fde858c` → `a04207e` → `56883af` →
this session's Slice 4 commit (not yet made — do that before considering this task closed).

**Immediate next actions:** Phase 3's non-`RiskEngine` backlog is complete. Slice 5 (`RiskEngine`)
is the last piece of Phase 3 and the highest-stakes work in the roadmap so far — the full approval
contract (APPROVED/REJECTED/APPROVED_WITH_REDUCED_SIZE), the stop-risk sizing formula, and
breakers. Given the user's "don't stop" instruction, proceed to it directly but scope it tightly
to what RISK.md actually specifies (its Invariants, Initial policy table, sizing formula, and
Approval contract sections verbatim) — do not invent additional checks or thresholds beyond what
RISK.md states, and write property tests per TESTING.md before considering any part of it done.
