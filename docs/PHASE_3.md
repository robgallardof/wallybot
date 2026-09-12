# Phase 3 implementation backlog

Status: Slice 1 (regime classification) implemented and verified on 2026-09-12. Slices 2-5 are a
documented backlog only — not started, not scaffolded as empty placeholders. See
[ARCHITECTURE](../ARCHITECTURE.md) for how Phase 3 fits the overall implementation sequence,
[RISK](../RISK.md) for the deterministic risk policy Slice 5 must implement, and
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
