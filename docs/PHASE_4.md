# Phase 4 implementation backlog

Status: Slice 1 (order intent + lifecycle state machine) and Slice 2 (`ExchangeGateway` port +
`FakeExchange` paper execution) implemented and verified on 2026-09-12/13.
Slices 3+ are a documented backlog only — not started. See [ARCHITECTURE](../ARCHITECTURE.md) for
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

**This session implements Slices 1 and 2.**

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

## Delivered: Slice 2 — `ExchangeGateway` port + `FakeExchange` paper execution

- `wallybot/domain/execution.py` (pure): the `ExchangeGateway` Protocol
  (`submit_order`/`cancel_order`/`lookup_order`/`list_fills`) per ARCHITECTURE.md's Contracts
  table entry ("Capabilities, balances, order lookup/submission/cancellation and fills; no
  withdrawal method") — no withdrawal method exists on it at all, not "guarded", simply absent,
  per ADR-004. Lookups are keyed by `client_order_id`, never a venue-assigned ID, because
  DATA.md says client order IDs are "deterministic within venue restrictions and mapped durably
  before submission" — this is what makes an ambiguous submission resolvable at all:
  `submit_order` can return `SubmissionOutcome.UNKNOWN` with no venue order ID, and a later
  `lookup_order` by the same `client_order_id` still finds the order, matching ADR-008's
  reconcile-before-retry and the order-lifecycle diagram's `UNKNOWN --> ACKNOWLEDGED: Lookup
  resolves`. Value types: `SubmissionResult`, `OrderLookup`, `CancelResult`, `Fill` — each
  validates its own shape (e.g. an `ACCEPTED` result must carry a `venue_order_id`, a `REJECTED`
  one must carry a `reason`).
- `wallybot/exchanges/fake.py`: `FakeExchange` now also implements `ExchangeGateway` alongside
  its existing `MarketDataProvider` capability (one class, two Protocols, structural typing).
  Per-currency `balances`, a configurable `fee_rate`, and three scripting dicts keyed by
  `client_order_id` (`submission_script`, `cancel_script`, `fill_script`) so tests can drive
  rejection, "accept-then-timeout" and partial fills deterministically, matching TESTING.md's
  "Inject a clock and scripted outcomes." An unscripted MARKET order fills fully and immediately
  at the current reference quote; an unscripted LIMIT order does not fill at all — there is no
  matching engine here, that belongs to backtesting (Phase 5), not this simulator. Validates
  quantity against `instrument.min_quantity` and balance sufficiency before accepting.
- `tests/contract/exchange_gateway_suite.py` + `tests/contract/test_fake_exchange_gateway.py`:
  shared contract suite mirroring `market_data_provider_suite.py`'s pattern, covering exactly this
  slice's acceptance evidence — submit-then-lookup round-trips, cancel races (clean cancel and
  fill-wins-the-race), accept-then-timeout resolved via lookup.
- `tests/unit/test_fake_exchange_execution.py`: `FakeExchange`-specific behavior — minimum-quantity
  and insufficient-balance rejection, balance settlement on a fill, unscripted limit orders never
  auto-filling, scripted multi-step partial fills (with a correctly weighted average fill price),
  a partial fill racing a cancel (the already-posted fill is retained, not erased), double-cancel
  of an already-filled order, and safe no-op behavior for an unknown `client_order_id` on both
  cancel and lookup.

Explicitly not built in Slice 2: no persistence (orders/fills live only in `FakeExchange`'s
in-memory dict for the lifetime of the test/process), no `ExecutionService` orchestration wiring
`OrderIntent`'s state machine to this gateway, no ledger, no real Kraken execution adapter (PAPER
mode never needs one — LIVE would get its own dedicated review, per `wallybot/exchanges/kraken.py`'s
own docstring).
