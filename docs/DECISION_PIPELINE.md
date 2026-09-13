# Decision pipeline: connecting Phase 3's signals to Phase 4's execution

Status: delivered and verified 2026-09-13. Not part of `docs/PHASE_2.md`/`PHASE_3.md`/`PHASE_4.md`'s
own backlogs — those each scoped themselves to "given an already-approved intent" (Phase 4) or
"a pure recommendation, nothing consumes it yet" (Phase 3). This is the glue between them: the
first place `scan_universe` (Phase 2) → regime/strategy/aggregation/allocation/risk (Phase 3) →
`OrderIntent`/`ExecutionService` (Phase 4) are actually wired into one call, and the first place a
real (PAPER) order gets created from real market data rather than a hand-built test fixture.

## What it does

`wallybot/application/decision_pipeline.py`'s `DecisionPipeline.run(portfolio_state,
risk_environment)`:

1. Discovers instruments and fetches candles/snapshots from an injected `MarketDataProvider`.
2. Runs the data-quality gate (`evaluate_series_quality`) per instrument — a `FAILURE` excludes an
   instrument from consideration entirely, before it ever reaches universe eligibility or scoring.
   This is a separate, earlier gate than universe eligibility (staleness/clock-skew/abnormal-return
   vs. history-length/volume/spread) that `scan_universe` itself does not perform.
3. Runs `scan_universe` (Phase 2) on the quality-passing instruments to rank finalists.
4. For each finalist, in order: `classify_regime` → the injected `Strategy.evaluate` →
   `SignalAggregator.aggregate` → (if not HOLD/SELL) `PortfolioAllocator.propose` → (if approved)
   `RiskEngine.evaluate` → (if not REJECTED) build an `OrderIntent` and call
   `ExecutionService.submit`.
5. Returns one `DecisionOutcome` per finalist — `order_status=None` for every instrument that
   didn't end up producing an order (HOLD, SELL, unapproved allocation, rejected risk), always
   with `reasons` explaining why. A HOLD/rejection is this pipeline's most common, fully correct
   result, not an error.

Only BUY is supported — `SimplePortfolioAllocator.propose` itself has no position data to size a
SELL against, so the pipeline checks for `Action.SELL` first and reports it as an ordinary
`DecisionOutcome` reason rather than letting the allocator raise.

## Real gap found and fixed while wiring this

`RiskAssessment` (Phase 3) only ever carried `final_notional` (a money amount), even though
RISK.md's own Approval contract says risk output includes "final quantity." Building an
`OrderIntent` requires a *quantity*, not a notional — re-deriving one outside the engine (a
different mid-price snapshot, different rounding) would let it silently drift from what risk
actually approved and checked against instrument minimums. Fixed by adding `final_quantity` to
`RiskAssessment` and having `DeterministicRiskEngine` return the quantity its own internal
instrument-precision step already computed, instead of discarding it. See `wallybot/domain/risk.py`
and the commit fixing this (`fe8b403`) for detail; this is exactly the kind of gap that only
surfaces when two independently-tested pieces are actually connected for the first time.

## What is explicitly out of scope

- **Computing `PortfolioState` / loss / drawdown / breaker state.** There is no equity or PnL
  tracker anywhere in this codebase yet. A caller supplies `PortfolioState` and `RiskEnvironment`
  from whatever it currently knows — same as `RiskContext` already required before this pipeline
  existed. Building that tracker is real future work, not a gap in this pipeline specifically.
- **Persisting the decision itself as a durable record.** DATA.md names a `decisions` collection;
  this pipeline generates a fresh `decision_id`/`risk_assessment_id` per attempt (via the injected
  `IdGenerator`) but nothing persists a `RiskAssessment` on its own — only the `OrderIntent` it
  produces is durable, through `ExecutionService`. A rejected/HOLD outcome today is visible only in
  the `DecisionOutcome` this call returns, not in Postgres. Losing that trail on process restart is
  a real limitation for counterfactual analysis (ARCHITECTURE.md: "Rejections are persisted for
  counterfactual analysis as well as approvals") that this pipeline does not yet meet.
- **Scheduling.** A caller decides when and how often `run()` executes; nothing here loops or
  wakes on a timer.
- **Multi-strategy consensus beyond whatever `SignalAggregator` is configured with**, and
  **SELL/position-reduction**, both blocked upstream in already-shipped Phase 3 pieces
  (`SimplePortfolioAllocator`), not something this pipeline works around.

## Verification

`tests/integration/test_decision_pipeline.py` (Testcontainers, real Postgres, real
`ExecutionService`/`FakeExchange`): a hand-built guaranteed-uptrend candle series produces a real
`FILLED` order with one balanced 4-posting ledger transaction end to end; a bucket already at its
capacity ceiling produces no order; an active risk breaker produces no order but is still reported
with its rejection reason. Full suite green (243 passed), `ruff`/`pyright` clean on every touched
file.
