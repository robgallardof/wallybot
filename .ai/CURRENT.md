# Current task

**Task:** Phase 4 kickoff ("Replay, paper execution, ledger and recovery under failures" per
`ARCHITECTURE.md`'s implementation sequence), tracked in `docs/PHASE_4.md`. User has explicitly
said to keep going without stopping to check in between slices for the rest of this session.

**Phase 2 status: complete except Slice 7 (streaming)** — deferred, needs an ADR-004 benchmark.
**Phase 3 status: complete (all 5 slices)** — see `docs/PHASE_3.md`.
**Phase 4 status: Slice 1 done and verified** (`OrderIntent` + lifecycle state machine, pure, no
persistence). Slices 2-6 are a documented, deliberately provisional backlog — Phase 4 needs a real
Postgres schema/migrations/transactional executor that Phases 2-3 never touched, and each of those
slices gets its own dedicated design pass when actually started, same as `RiskEngine` did.

**Delivered this session (chronological, latest last):**
- Fixed the Vite→Next.js migration, DTO/SRP refactor (commits `b15a0dc`, `7e16332`).
- Phase 2 Slices 1-6, 8, 9 (commits `2d75de8` → `e0eb7f5`) — see `docs/PHASE_2.md`.
- Phase 3 Slices 1-5, Phase 3 complete (commits `fde858c` → `639386e`) — see `docs/PHASE_3.md`.
  Along the way: found Kraken's market-data API needs no credentials (corrected an assumption),
  and found/fixed a real `wallybot/domain/` layering violation (extracted `wallybot/domain/
  quality.py`) — both logged in `.ai/DECISIONS.md`.
- `docs/stats/testing.md` updated with real current test counts (commit `195d0ab`).
- Phase 4 Slice 1 (not yet committed): `wallybot/domain/order.py` (`OrderStatus` — 12 states, a
  transition table that is a direct edge-for-edge encoding of `docs/diagrams/order-lifecycle.md`,
  `OrderIntent`, `InvalidOrderTransition`). `tests/unit/test_order.py`,
  `tests/property/test_order_invariants.py` (Hypothesis random-walk, same style as the existing
  Control state-machine property test).

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 194
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed
(`wallybot/domain/order.py` imports only stdlib + `wallybot.domain.market`).

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → `e0eb7f5` → `fde858c` → `a04207e` → `56883af` →
`b5710a9` → `639386e` → `195d0ab` → this session's Phase 4 Slice 1 commit (not yet made — do that
before considering this task closed).

**Immediate next actions:** Phase 4 Slice 2 (`ExchangeGateway` port extension for order submit/
cancel/lookup/fills, plus a `FakeExchange` paper-execution implementation satisfying it) is next
per `docs/PHASE_4.md`. It's still buildable without real Kraken trading access (PAPER mode uses
the simulator, matching TESTING.md's seeded-`FakeExchange` requirement: "balances, minimums,
market/limit capabilities, spread, fees, slippage, latency, partial fills, rejection, disconnect
and accept-then-timeout behavior" — a materially bigger `FakeExchange` extension than anything
built so far, worth its own careful design rather than assuming the Phase 2 shape carries over
unchanged).
