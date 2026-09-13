# Phase 3 implementation backlog

Status: **all five slices implemented and verified on 2026-09-12.** Phase 3 is complete. See
[ARCHITECTURE](../ARCHITECTURE.md) for how Phase 3 fits the overall implementation sequence,
[RISK](../RISK.md) for the deterministic risk policy Slice 5 implements, and
[PHASE_2](PHASE_2.md) for the completed market/data/scanner phase this builds on.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | Regime classification from features (pure, versioned) | Unit tests: each regime label reachable from a synthetic momentum value |
| 2 | `Strategy` port + one deterministic strategy → `StrategySignal` | Unit tests: pure recommendation, cannot submit orders (no such method exists) |
| 3 | `SignalAggregator` (deterministic weighting, HOLD on invalid quorum) | Unit tests: agreement/disagreement/invalid-quorum cases |
| 4 | `PortfolioAllocator` (proposed allocation under bucket/asset/cluster capacity, using RISK.md's given Core/Growth/Speculative 70/20/10 initial policy) | Unit tests against RISK.md's stated ceilings |
| 5 | `RiskEngine` (full approval contract, sizing formula, breakers) | **Gets its own dedicated planning session** — property tests targeting ≥95% branch coverage per TESTING.md, every rejection reason in RISK.md's Invariants table tested independently and in combination |

**This is the highest-stakes phase in the roadmap so far.** `RISK.md` is extraordinarily explicit
about `RiskEngine` and says outright: "Missing required limits fail closed; do not invent
universally safe market thresholds." Slice 5 in particular must not be rushed into the same pass
as lower-stakes work — it gets its own dedicated design/review pass when the user is ready for it.

## Delivered: Slice 1 — regime classification

- `wallybot/domain/regime.py`: `Regime` (`TRENDING_UP`, `TRENDING_DOWN`, `RANGING`, `RISK_OFF` —
  `RISK_OFF` named explicitly because RISK.md calls it out: "Neutral and risk-off regimes may
  reduce ceilings", even though nothing consumes that reduction yet), `RegimeClassification`
  (instrument, as_of, version, regime, a human-readable reason string — matching
  `wallybot/data/quality.py`'s `QualityIssue.evidence` pattern of always explaining *why*), and
  `classify_regime(vector, risk_off_threshold)` — reads the `momentum_<window>` feature Slice 8's
  `SimpleFeatureEngine` already produces, raises `ValueError` if that feature is missing (fail
  loud, not silent, same as `LookaheadError`).
- No new port/Protocol: `ARCHITECTURE.md`'s Contracts table doesn't name a "RegimeClassifier" port
  (unlike `Strategy`, `SignalAggregator`), so this is a plain pure rule — matching
  `wallybot/market/universe.py` and `wallybot/data/quality.py`'s existing style, since there's only
  one classification rule to run, not multiple adapters to choose between.
- `tests/unit/test_regime.py`: one test per reachable regime label, the exact-threshold boundary
  case, missing-feature rejection, and nonpositive-threshold rejection.

Explicitly not built in Slice 1: nothing consumes a `RegimeClassification` yet (no strategy reads
it, no risk ceiling changes because of it) — that arrives with Slices 2 and 5 respectively. No
volatility-based or multi-feature regime logic; momentum alone is deliberately the simplest
possible starting rule until a real strategy needs more.

## Delivered: Slice 2 — `Strategy` port + trend-following strategy

- `wallybot/domain/strategy.py`: `Action` (`BUY`/`SELL`/`HOLD`), `StrategyContext` (instrument,
  features, regime, as_of — everything a pure strategy needs, nothing an execution capability
  would need), `StrategySignal` (instrument, strategy_id, version, action, confidence in `[0, 1]`,
  as_of, reason), and the `Strategy` protocol (`evaluate(context) -> StrategySignal`) explicitly
  named in `ARCHITECTURE.md`'s Contracts table: "Pure recommendation; cannot submit orders or
  mutate balances." There is no method on anything in this module resembling order submission —
  nothing here for a future caller to misuse even by accident.
- `wallybot/strategies/trend_following.py` (new package, explicitly named in `ARCHITECTURE.md`'s
  planned layout): `TrendFollowingStrategy` — the first concrete strategy, DRAFT status per
  RISK.md's promotion ladder. Maps regime directly to action (`TRENDING_UP`→BUY,
  `TRENDING_DOWN`→SELL, `RANGING`/`RISK_OFF`→HOLD) and derives confidence from `|momentum|` capped
  at 1. Validates that the regime classification and feature vector actually belong to the context
  instrument before using them (a caller wiring bug there would otherwise silently produce a
  signal based on the wrong instrument's data).
- `tests/unit/test_strategy.py` (value validation: confidence bounds, required fields) and
  `tests/unit/test_trend_following.py` (one test per regime→action mapping, confidence capping,
  cross-instrument mismatch rejection, missing-feature rejection).

Explicitly not built in Slice 2: no second strategy, no strategy registry/versioning migration
path, no `SignalAggregator` yet to combine multiple strategies' signals (Slice 3) — a single
strategy's signal isn't "consensus," it's just one opinion, deliberately not treated as more than
that anywhere downstream yet since nothing downstream (allocation, risk) exists to consume it.

## Delivered: Slice 3 — `SignalAggregator`

- `wallybot/domain/aggregation.py`: `AggregatedSignal` (instrument, action, confidence in `[0,1]`,
  version, as_of, the full tuple of `contributing_signals` for auditability, and a reason string)
  and the `SignalAggregator` protocol (`aggregate(signals, as_of) -> AggregatedSignal`) — matches
  `ARCHITECTURE.md`'s Contracts table verbatim: "Deterministic weighting, agreement and
  disagreement; HOLD on invalid quorum."
- `wallybot/signals/weighted_aggregator.py` (new package, explicitly named in `ARCHITECTURE.md`'s
  planned layout): `WeightedSignalAggregator` — fixed, versioned per-strategy weights; computes
  confidence-weighted BUY vs SELL totals against total participating weight. Returns HOLD (not a
  coin-flip pick) in **two** distinct cases, each with its own reason string: quorum not met (too
  few signals), or agreement ratio below a configured minimum (signals disagree, or barely edge
  out each other) — a real strategy conflict is treated as "no signal," never resolved by
  tie-breaking logic. Raises loudly on an unconfigured strategy ID or mismatched instruments,
  rather than silently ignoring or zero-weighting a signal that shouldn't have been passed in.
- `tests/unit/test_aggregation.py` (value validation) and
  `tests/unit/test_weighted_aggregator.py`: full agreement → BUY at full confidence, full
  disagreement → HOLD, weak agreement below threshold → HOLD, a strong weighted majority
  overriding a lone dissenting signal → BUY at the correct computed confidence, quorum-not-met →
  HOLD, and rejections for an unconfigured strategy, mismatched instruments, empty input, and each
  constructor validation rule.

Explicitly not built in Slice 3: no `PortfolioAllocator` or `RiskEngine` consuming an
`AggregatedSignal` yet (Slices 4-5) — an aggregated BUY/SELL/HOLD recommendation is still just a
recommendation until something proposes a position size and something else approves it.

## Delivered: Slice 4 — `PortfolioAllocator`

- `wallybot/domain/portfolio.py`: `Bucket` (`CORE`/`GROWTH`/`SPECULATIVE`), `PortfolioPolicy`
  (versioned; bucket targets that must sum to exactly 1, speculative operating/absolute maxima,
  single-speculative-asset maximum, max open positions — **every default comes from RISK.md's own
  Initial Policy table, none invented**: 70/20/10 targets, 10% operating / 15% absolute speculative
  ceiling, 3% single speculative asset, 1 open position), `PortfolioState` (equity, per-bucket and
  per-asset exposure grouped across venues per RISK.md, open position count), `AllocationProposal`
  (approved/rejected with reasons; a dataclass invariant enforces approved⇒positive notional and
  rejected⇒zero notional, so the two fields can never silently disagree), and the
  `PortfolioAllocator` protocol (`propose(signal, bucket, state, policy, as_of) ->
  AllocationProposal`) — matches `ARCHITECTURE.md`'s one-line Contracts description: "Proposed
  allocation under bucket, asset and cluster capacities."
- `wallybot/portfolio/simple_allocator.py` (new package, explicitly named in `ARCHITECTURE.md`'s
  planned layout): `SimplePortfolioAllocator` — proposes bucket headroom scaled by the signal's
  confidence, then (for `SPECULATIVE` only) further caps by the operating ceiling and the
  single-asset ceiling. **Deliberately targets only the operating ceiling, never the absolute
  one** — RISK.md: "The 15% absolute ceiling does not automatically authorize an increase from
  10%. Such a change needs reviewed configuration, fresh MFA and explicit operator action"; nothing
  in this allocator has a path to that ceiling. A `SELL` signal raises rather than silently
  no-op'ing, because reducing/closing a position needs real position data this phase has no
  representation for yet (that's Phase 4 ledger territory) — a strategy proposing a sell here would
  otherwise be silently ignored, which is worse than a loud error.
- `tests/unit/test_portfolio.py` (value validation, including the `RISK.md`-matching default
  policy) and `tests/unit/test_simple_allocator.py`: HOLD/SELL handling, max-open-positions,
  bucket-ceiling-reached, a full `CORE` allocation computed by hand, the speculative single-asset
  cap taking priority over a wider bucket room, a synthetic wider-bucket-target policy isolating
  the operating-ceiling branch specifically, and the single-speculative-asset-ceiling branch.

Explicitly not built in Slice 4: the actual stop-risk position-sizing formula from RISK.md's "Loss
calculations and sizing" section (needs entry/stop price and a risk-budget concept this phase has
no representation for) — that belongs to `RiskEngine` (Slice 5), which also has final approve/
reject/reduce authority over whatever this allocator proposes. No cluster-level concentration
(only bucket + single-asset) — nothing yet defines what a "cluster" grouping is. No `AI` advisory
step from the trade-decision flow — that is Phase 6.

**Slice 5 (`RiskEngine`) remains a dedicated, separate planning item** — it is the authoritative
approval gate for real financial exposure and RISK.md is explicit that its thresholds must never be
invented ad hoc.

## Delivered: Slice 5 — `RiskEngine`

Scoped to exactly what this codebase can faithfully implement today from RISK.md's own stated
Invariants, Initial Policy table and Approval contract — nothing invented, nothing skipped
silently. See the module docstrings in `wallybot/domain/risk.py` and
`wallybot/risk/deterministic_risk_engine.py` for the full reasoning; summary:

- `wallybot/domain/risk.py`: `RiskDecision` (`APPROVED`/`REJECTED`/`APPROVED_WITH_REDUCED_SIZE`),
  `ExchangeStatus`, `RiskPolicy` (version, and RISK.md's given max daily/weekly loss, max
  drawdown, and max spread — spread has **no default**, since RISK.md explicitly says
  liquidity/spread-class limits "must be configured... Missing required limits fail closed; do
  not invent universally safe market thresholds" — every `RiskPolicy` field is required at
  construction, never optional-with-a-guess), `RiskContext` (everything RISK.md's Approval
  contract says Risk *receives*: control status, portfolio state/policy, quality result,
  snapshot, exchange status, reconciliation health, active breakers, daily/weekly/drawdown loss,
  as_of, expiry — RiskEngine computes none of this itself), `RiskAssessment` (decision, final
  notional, version, as_of, expires_at, reasons — a dataclass invariant enforces REJECTED⇒zero
  notional, everything else⇒positive notional, and reasons is never empty, so an assessment can
  never claim a decision with no evidence), and the `RiskEngine` protocol.
- `wallybot/risk/deterministic_risk_engine.py`: `DeterministicRiskEngine` — checks run in the
  order RISK.md lists (allocator approval → mode/authority → fresh data → exchange status →
  reconciliation → breakers → daily/weekly/drawdown losses, `>=` not `>` since "Equality at a
  limit triggers the breaker" → spread), then re-derives bucket/asset capacity **authoritatively**
  (never trusting the allocator's proposal blindly — this is the final word, and may reduce size
  here) and applies instrument precision/minimum-quantity rounding (may reduce size again). A
  reduction at either of the last two steps yields `APPROVED_WITH_REDUCED_SIZE`; a reduction to
  below the instrument's minimum tradable quantity is a full `REJECTED`, matching "Zero-sized
  approvals are rejected" — never an approval for zero.
- `tests/unit/test_risk.py` (value validation) and
  `tests/unit/test_deterministic_risk_engine.py`: one test per blocking check fired independently,
  the exact-equality-at-limit boundary for daily/weekly/drawdown losses, a hand-computed
  capacity-driven size reduction, a hand-computed instrument-precision-driven size reduction, the
  single-speculative-asset ceiling taking priority, and the zero-sized-rounds-to-rejection case.
- `tests/property/test_risk_invariants.py`: a Hypothesis property test (per TESTING.md's call for
  risk-code property coverage) generating losses, drawdown, bucket exposure, proposed notional and
  spread across their valid ranges, asserting the core shape invariant holds for every generated
  combination: `REJECTED` always has zero notional, anything else always has a positive notional
  that never exceeds what was proposed, expiry is always strictly after `as_of`, and every
  assessment carries at least one reason.
- **Found and fixed a real architecture-layering bug in the process**: `wallybot/domain/risk.py`
  initially imported `QualityReport` from `wallybot/data/quality.py`, which would have made
  `wallybot/domain/` depend on a capability package — backwards. Extracted the pure value types
  into `wallybot/domain/quality.py` instead (see `.ai/DECISIONS.md`).

**Explicitly out of scope, documented in the module docstrings, not silently missing:**
volatility/correlation limits (nothing in this codebase computes volatility yet — only momentum,
Phase 3 Slice 8); any AI-related check (no AI provider exists — Phase 6); the *mechanism* behind
reconciliation health and breaker state (Phase 4 ledger/execution infrastructure — `RiskContext`
receives these as already-computed booleans/sets, per RISK.md's own description of what Risk
*receives* rather than computes); cluster-level concentration (only bucket + single-asset, same
scope boundary as Slice 4); the full emergency-operations action set (`PAUSE NEW TRADES`,
`CANCEL OPEN ORDERS`, `CLOSE ALL POSITIONS`, `EMERGENCY STOP` — these are operator-triggered
actions on *existing* exposure, not part of evaluating a *new* proposal).

**Phase 3 is now complete.** Next per `ARCHITECTURE.md`'s implementation sequence is Phase 4:
"Replay, paper execution, ledger and recovery under failures" — the first phase requiring real
persistence (order intents, fills, ledger postings) beyond anything built so far.
