# PAPER trading: the live decision loop

Status: a real, running PAPER decision loop exists and places PAPER orders end-to-end
(`wallybot/application/decision_loop.py`'s `run_decision_tick`, called every 300 seconds by
`apps/api/main.py`'s `_decision_loop` background task). LIVE trading does not exist in this
codebase in any form — see "LIVE does not exist" below before reading anything else on this page.

This document describes what the loop actually does, traced from the code that runs in
production, not from the original specification. For the deterministic risk policy itself (limits,
breaker types, approval contract) see [RISK.md](../RISK.md); for the security controls gating
sensitive actions see [SECURITY.md](../SECURITY.md); for the schema/ledger/reconciliation
guarantees see [DATA.md](../DATA.md); for the full target architecture see
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Who runs the loop, and when

`_decision_loop` (`apps/api/main.py`) is a `while True` background task started in `create_app`'s
lifespan, alongside `_market_ingestion_loop` and `_price_consensus_loop` — only `apps/api` has
internet egress to reach Kraken, so this is the one process that can run it
(`docker-compose.yml`'s `operational`/`research` networks are `internal: true`). Every
`DECISION_INTERVAL_SECONDS = 300` it:

1. Reads `ControlRow` and the single admin account. If setup isn't complete, status isn't
   `RUNNING`, environment isn't `PAPER`, or there is no admin yet, it sleeps and retries — it never
   runs against an unconfigured or paused system.
2. Calls `run_decision_tick` (`wallybot/application/decision_loop.py`) for that admin's PAPER
   account (`paper_account_id(admin_id)`).
3. Logs `DECISION_TICK_COMPLETED` with instruments evaluated, orders placed, reconciliation health
   and active breakers, and updates the `DECISION_TICKS`/`ORDERS_PLACED`/`RECONCILIATION_HEALTHY`/
   `ACTIVE_BREAKERS` Prometheus metrics. A tick that raises is caught, logged as
   `DECISION_TICK_FAILED`, and the loop keeps running — one bad tick never kills the process.

There is exactly one account (single-admin, matching this codebase's current single-user
administration — see `docs/PENDING.md` Fase 1) and one bucket per tick: `BUCKET = Bucket.CORE`,
the most conservative of RISK.md's three buckets. There is no per-instrument bucket assignment
schema yet, so GROWTH/SPECULATIVE never receive orders from this loop today.

## One tick, traced end to end

`run_decision_tick` (`wallybot/application/decision_loop.py`):

1. **Resync simulated balances from the ledger.** `paper_gateway.balances` (a `FakeExchange`) is
   overwritten from `PortfolioRepository.list_balances` every tick — the ledger, not
   `FakeExchange`'s own in-memory state, is the source of truth, so a funding transaction posted
   between ticks (`POST /api/portfolio/fund`) is picked up correctly.
2. **Reconciliation sweep.** `ReconciliationService.sweep("PAPER")` resolves every non-terminal
   order intent against the gateway before anything else runs (see "Reconciliation" below).
3. **Equity assessment.** `assess_equity` (`wallybot/application/equity_tracker.py`) computes
   current equity, daily loss, weekly loss and drawdown from `wallybot/domain/equity.py`'s
   snapshot history — the equity/PnL tracker `DecisionPipeline`'s own docstring says did not exist
   until this was built.
4. **Breaker evaluation.** `breakers_to_trip` (`wallybot/domain/breaker.py`) checks that tick's
   fresh daily loss/weekly loss/drawdown against `RISK_POLICY` and reconciliation health, and any
   newly-tripped breaker is persisted via `BreakerRepository.trip` (idempotent — a repeat trip
   while already active keeps the original reason/time). Every currently active breaker (including
   ones tripped on an earlier tick, even if the underlying metric has since recovered) feeds
   `RiskEnvironment.active_breakers` — RISK.md: "a scheduler cannot silently reset a breaker at
   midnight."
5. **`DecisionPipeline.run`** (`wallybot/application/decision_pipeline.py`), the real
   regime → strategy → risk → allocator → execution composition:
   - Discovers instruments, fetches candles/snapshots, runs `evaluate_series_quality` per
     instrument — anything with `QualityStatus.FAILURE` is dropped before scoring.
   - `scan_universe` ranks the remaining candidates and returns up to `max_finalists` (5) finalists.
   - For each finalist: `classify_regime` (`wallybot/domain/regime.py`) →
     `TrendFollowingStrategy.evaluate` (the only strategy wired — see
     [STRATEGIES.md](STRATEGIES.md)) → `WeightedSignalAggregator.aggregate` (single-strategy
     weight of 1, so this is pass-through today, not real multi-strategy consensus) → HOLD ends the
     pipeline for that instrument with no order.
   - A non-HOLD signal goes to `SimplePortfolioAllocator.propose`. BUY and SELL both flow through
     the same path — a SELL is sized as a reduction of the instrument's own currently-held
     exposure, never a short (there is no short-selling capability anywhere in this codebase).
   - An approved allocation proposal goes to `DeterministicRiskEngine.evaluate` against
     `RiskContext` (portfolio state, quality, snapshot, exchange status, reconciliation health,
     active breakers, daily/weekly loss, drawdown). `RiskDecision.REJECTED` ends the pipeline with
     no order — this is `DecisionPipeline`'s own stated "most common, fully correct outcome," not a
     failure.
   - An approved assessment builds an `OrderIntent` (always `OrderKind.MARKET`; there is no LIMIT
     order path from this loop) and calls `ExecutionService.submit`.
6. Returns a `DecisionTickResult` with per-instrument outcomes, reconciliation health/unknown-order
   count, and the active breaker list — this is exactly what `_decision_loop` logs and turns into
   metrics.

## Execution and the order lifecycle

`ExecutionService.submit` (`wallybot/application/execution_service.py`) implements ADR-008: persist
the intent, transition it to `SUBMITTING` durably *before* calling the gateway, then call
`FakeExchange.submit_order`. A `REJECTED` gateway result is recorded as `REJECTED`. An `UNKNOWN`
result is left at `UNKNOWN` — `submit()` never retries it; only `reconcile()` can move an order out
of `UNKNOWN`, and only by asking the gateway what it actually knows. An acknowledged order is
observed via `_observe`, which looks up fills idempotently (`UnitOfWork.fill_exists` first) so a
repeated observation never double-posts a fill or its ledger transaction. `cancel()` follows the
identical discipline: record `CANCEL_REQUESTED` before calling the gateway, then resolve through the
same lookup-based path rather than trusting the gateway's own cancel-result outcome.

A fill's ledger transaction (`build_fill_ledger_transaction`,
`wallybot/application/ledger_postings.py`) commits together with the fill row and the position
projection change, per DATA.md's balanced-postings guarantee.

## Reconciliation

`ReconciliationService.sweep` (`wallybot/application/reconciliation_service.py`) composes
`ExecutionService.reconcile_order` across every open order for an environment — it adds no new
resolution logic of its own. One order's failure is recorded (`ReconciliationOutcome.error`) and
does not abort the sweep for the rest. It runs at the start of every decision tick, per DATA.md's
"run at startup ... periodically" requirement — but only for that one trigger; there is no separate
startup-time or post-ambiguity sweep beyond what the tick loop already provides.

Explicitly out of scope (per the module's own docstring): balance/position comparison against a
real venue (`ExchangeGateway` has no balance-fetching method — `FakeExchange` is the only gateway
that exists), persisted discrepancy evidence beyond the returned outcomes, and pagination over
exchange history. All of these matter more once a real venue exists; today's sweep only reconciles
what this codebase's own orders already track.

## Persistent circuit breakers

`wallybot/domain/breaker.py` models four breaker types: `DAILY_LOSS`, `WEEKLY_LOSS`, `DRAWDOWN`,
`RECONCILIATION`. Each is a single latched state (this system has one account) with
`reason`/`tripped_at`/`cleared_at`/`cleared_by`. A trip is idempotent; a clear requires the breaker
to currently be tripped. `GET /api/risk/breakers` lists all of them; `POST
/api/risk/breakers/{type}/clear` requires Admin + fresh MFA (see [SECURITY.md](../SECURITY.md)) and
records a `BREAKER_CLEARED` audit row.

RISK.md's fuller breaker taxonomy — stale data, abnormal spread/volatility, exchange outages,
repeated execution errors, unknown orders, mismatches, DB failure, clock drift — has **no trigger
wiring yet**. Only daily loss, weekly loss, drawdown and reconciliation health are evaluated each
tick. This is stated in `wallybot/domain/breaker.py`'s own module docstring, not silently implied
as covered.

## What this loop does not do

- **No LIVE trading exists.** See the next section.
- **No SHORT selling.** SELL only ever reduces an existing long position; there is no negative
  inventory anywhere in the risk or allocation code.
- **Only MARKET orders.** The loop never builds a LIMIT `OrderIntent`; `ExecutionService.cancel`
  exists but has no natural trigger from this automated pipeline today (it becomes load-bearing
  once a LIMIT path or a real asynchronous venue exists).
- **Single bucket, single account, single strategy.** CORE only, one admin account, one strategy
  (`TrendFollowingStrategy`) behind a pass-through aggregator — see
  [STRATEGIES.md](STRATEGIES.md).
- **No AI in this path.** The loop never calls an `AIProvider` — see [AI.md](AI.md).
- **The decision itself is not persisted as its own durable record.** `DecisionPipeline` generates
  a fresh `decision_id`/`risk_assessment_id` per attempt, but nothing writes a standalone
  `RiskAssessment` row; only the `OrderIntent` it produces (when approved) is durable via
  `ExecutionService`. DATA.md's `decisions` table is not populated by this loop.

## LIVE does not exist

There is no LIVE adapter, no Kraken private-API gateway, no withdrawal-disabled key verification,
and no lease/rearm mechanism anywhere in this codebase. `docs/PENDING.md`'s Fase 9 ("preparación
LIVE, solamente tras los gates") is entirely unstarted, by design — every item in it is unchecked.
`DecisionPipelineConfig.environment` accepts the literal `"LIVE"` as a type, but nothing ever
constructs a pipeline with it; `_decision_loop` hardcodes `"PAPER"` end to end.

Before LIVE can even be attempted, [RISK.md](../RISK.md)'s "Evidence before LIVE" section and
[SECURITY.md](../SECURITY.md)'s LIVE-activation requirements (trade-only key verification with
withdrawals disabled, fresh TOTP, explicit human confirmation of account/environment, a revocable
lease that requires reconciliation and operator rearm after every restart) must all be satisfied —
this document does not restate those gates, it only confirms that none of the code they gate exists
yet.
