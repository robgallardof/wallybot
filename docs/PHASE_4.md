# Phase 4 implementation backlog

Status: Slice 1 (order intent + lifecycle state machine) implemented and verified on 2026-09-12.
Slices 2+ are a documented backlog only — not started. See [ARCHITECTURE](../ARCHITECTURE.md) for
how Phase 4 fits the overall implementation sequence, [DATA](../DATA.md) for the ledger/
reconciliation rules later slices must implement, and [PHASE_3](PHASE_3.md) for the completed
signals/allocation/risk phase this builds on.

**Phase 4 is a substantial jump in scope from Phases 2-3.** Everything through `RiskEngine` was
pure domain/capability code (plus one Redis cache and one filesystem writer). Phase 4 —
"Replay, paper execution, ledger and recovery under failures" — needs a real database schema
(order_intents, orders, fills, ledger_accounts/transactions/postings, position_lots,
reconciliations, outbox — DATA.md's Operational schema plan), migrations, and a transactional
executor. Each of those is its own dedicated design pass, the same discipline `RiskEngine` got in
Phase 3 — this backlog is deliberately provisional past Slice 1 and will be refined as each slice
is actually designed, not committed to upfront.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | `OrderIntent` + `OrderStatus` lifecycle state machine (pure, no persistence) | Unit + property tests: every diagram edge reachable, no illegal transition possible |
| 2 | `ExchangeGateway` port extension (submit/cancel/lookup/fills) + `FakeExchange` paper-execution implementation | Contract suite: submit-then-lookup round-trips, cancel races, accept-then-timeout |
| 3 | Ledger domain model (`LedgerAccount`, `LedgerTransaction`, `LedgerPosting` — balanced double-entry) | Property tests: postings always balance per currency, never mix units |
| 4 | Real PostgreSQL schema + Alembic migration for order/fill/ledger tables, `UnitOfWork` | Integration tests: real Postgres via Testcontainers, unique-constraint dedup |
| 5 | `ExecutionService` (durable claim, SUBMITTING before network call, UNKNOWN resolution, reconcile-before-retry per ADR-008) | Failure-injection tests: crash before/after SUBMITTING, ambiguous timeout, no duplicate fills |
| 6 | Reconciliation (fetch/dedupe/compare exchange state, persist discrepancies) | Integration tests against `FakeExchange`'s scripted outcomes (TESTING.md) |

**This session implements Slice 1 only.**

## Delivered: Slice 1 — `OrderIntent` + lifecycle state machine

- `wallybot/domain/order.py`: `OrderStatus` (12 states — `CREATED`, `VALIDATED`, `REJECTED`,
  `SUBMITTING`, `SUBMITTED`, `UNKNOWN`, `FAILED`, `ACKNOWLEDGED`, `PARTIALLY_FILLED`,
  `CANCEL_REQUESTED`, `CANCELLED`, `FILLED`) and a private transition table that is a direct,
  edge-for-edge encoding of `docs/diagrams/order-lifecycle.md`'s state diagram — not a
  reinterpretation of it. `can_transition(current, next) -> bool` and `OrderIntent.transition_to`
  (raises `InvalidOrderTransition` rather than allowing an illegal jump — e.g. `CREATED` straight
  to `FILLED`). `UNKNOWN` can only resolve to what a lookup could actually observe, or back to
  `VALIDATED` for "proven absent and safe retry after risk" (the diagram's own words) — never
  straight into a filled/acknowledged state without going through a lookup, matching ADR-008's
  "reconcile-before-retry."
- `OrderIntent` (frozen; every mutation returns a new instance via `transition_to`, never mutates
  in place) carries exactly what DATA.md's "Order intents contain..." sentence lists: account,
  mode (`environment: Literal["PAPER","LIVE"]`), instrument, side, type, quantity, price
  constraints, decision ID, client order ID, idempotency key, expiry, risk assessment ID and
  configuration versions. Validates market orders never carry a limit price and limit orders
  always require one, all identifiers are non-empty, quantity/limit_price are positive, and
  `expires_at` is after `created_at`.
- `tests/unit/test_order.py`: value validation, the full happy-path sequence
  (`CREATED→VALIDATED→SUBMITTING→SUBMITTED→ACKNOWLEDGED→PARTIALLY_FILLED→FILLED`), the illegal
  `CREATED→FILLED` jump, `UNKNOWN→VALIDATED` safe-retry, `UNKNOWN` cannot re-enter `SUBMITTING`,
  terminal states have zero outgoing transitions, and `transition_to` does not mutate the
  original instance.
- `tests/property/test_order_invariants.py`: a Hypothesis random walk (same style as the existing
  `test_control_sequence_never_enters_live`) that only ever takes moves `can_transition` already
  approves, across 200 generated sequences, and confirms it never raises, never leaves a terminal
  status, and always lands exactly where requested.

Explicitly not built in Slice 1: no `ExchangeGateway` calls, no persistence, no `ExecutionService`
orchestration, no ledger. `OrderIntent` is a value a future executor will create, transition and
persist — this slice only guarantees the state machine itself cannot be driven into an
impossible configuration.
