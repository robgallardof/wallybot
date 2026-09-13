# Current task

**Task:** Continuing past Phase 2 into Phase 3 ("Scoring, regimes, strategies, allocation and
tested deterministic risk" per `ARCHITECTURE.md`'s implementation sequence), tracked in
`docs/PHASE_3.md` (same ordered-slice format as Phase 1/2).

**Phase 2 status: complete except Slice 7 (streaming)**, deferred pending the ADR-004
WebSocket-vs-CCXT-Pro benchmark — a materially different, larger piece of work.

**Phase 3 status: Slices 1-3 done and verified** (regime classification; `Strategy` port +
`TrendFollowingStrategy`; `SignalAggregator`). Slices 4-5 are a documented backlog only. **Slice 5
(`RiskEngine`) is explicitly flagged to get its own dedicated planning session** — `RISK.md` is
extraordinarily detailed and says "do not invent universally safe market thresholds"; it must not
be rushed into the same pass as lower-stakes work.

**Delivered this session (chronological, latest last):**
- Fixed the Vite→Next.js migration, DTO/SRP refactor (commits `b15a0dc`, `7e16332`).
- Phase 2 Slices 1-6, 8, 9 (commits `2d75de8`, `fa2125b`, `40bf7f1`, `4f62804`, `c0567ae`,
  `1bf0b3d`, `853cb4b`, `e0eb7f5`) — see `docs/PHASE_2.md` for full detail per slice.
- **Correction logged in `.ai/DECISIONS.md`:** initially assumed the Kraken adapter (Slice 6)
  needed user-provided credentials; wrong — Kraken's market-data endpoints are public. Verify a
  third-party API's actual auth requirements before reporting something as blocked on credentials.
- Phase 3 Slice 1 (`fde858c`): `wallybot/domain/regime.py` (`Regime`, `RegimeClassification`,
  `classify_regime`). `tests/unit/test_regime.py`.
- Phase 3 Slice 2 (`a04207e`): `wallybot/domain/strategy.py` (`Action`, `StrategyContext`,
  `StrategySignal`, `Strategy` protocol) and `wallybot/strategies/trend_following.py`
  (`TrendFollowingStrategy`).
- Phase 3 Slice 3 (not yet committed): `wallybot/domain/aggregation.py` (`AggregatedSignal`,
  `SignalAggregator` protocol) and `wallybot/signals/weighted_aggregator.py`
  (`WeightedSignalAggregator` — confidence-weighted BUY/SELL totals, HOLD on quorum-not-met or
  weak agreement, raises on unconfigured strategy or mismatched instruments).
  `tests/unit/{test_aggregation,test_weighted_aggregator}.py`.

**Verified:** `uv run pytest tests/unit tests/integration tests/property tests/contract -q` → 122
passed. `uv run ruff check`, `uv run pyright` → clean. Domain purity confirmed.

**Branch:** `master`. Commits: `b15a0dc` → `7e16332` → `2d75de8` → `fa2125b` → `40bf7f1` →
`4f62804` → `c0567ae` → `1bf0b3d` → `853cb4b` → `e0eb7f5` → `fde858c` → `a04207e` → this session's
Slice 3 commit (not yet made — do that before considering this task closed).

**Immediate next actions:** Confirm with the user before Phase 3 Slice 4 (`PortfolioAllocator` —
proposed allocation under bucket/asset/cluster capacity, using `RISK.md`'s given Core/Growth/
Speculative 70/20/10 initial policy). This is a step up in stakes from Slices 1-3 (it touches
`RISK.md`'s stated ceilings, even if it's not the final approval authority) — check in with the
user before starting it, and treat Slice 5 (`RiskEngine`) as needing its own separate, later
dedicated planning pass regardless of how Slice 4 goes.
