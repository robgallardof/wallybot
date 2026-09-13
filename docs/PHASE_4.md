# Phase 4 implementation backlog

Status: Slice 1 (order intent + lifecycle state machine), Slice 2 (`ExchangeGateway` port +
`FakeExchange` paper execution), Slice 3 (balanced double-entry ledger value types), Slice 4
(real PostgreSQL schema + migration + `UnitOfWork`) and Slice 5 (`ExecutionService`) implemented
and verified on 2026-09-12/13.
Slice 6 is a documented backlog only — not started. See [ARCHITECTURE](../ARCHITECTURE.md) for
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

**This session implements Slices 1 through 5.**

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

## Delivered: Slice 3 — balanced double-entry ledger value types

- `wallybot/domain/ledger.py` (pure): `AccountPurpose` (`CASH`/`POSITION`/`CLEARING`/`FEE`),
  `LedgerAccount` (account_id + currency + purpose), `LedgerPosting` (a signed `Decimal` amount
  against one account; positive increases the account's balance, negative decreases it — this
  encodes debit/credit equality as "signed amounts sum to zero" rather than separate debit/credit
  columns, which is equivalent but simpler to validate and property-test). A zero-amount posting
  is rejected outright (DATA.md gives no reason to ever persist one; it would only hide a bug).
  `LedgerTransaction` groups postings and enforces DATA.md's "Enforce debit/credit equality per
  asset/currency within a journal transaction at commit": for every currency its postings touch,
  those signed amounts must sum to exactly zero. Grouping by currency *before* summing is what
  "never adds BTC units to USD units" means in code — a BTC leg can never cancel a USD leg.
  Requires at least two postings (single-entry isn't double-entry) and an aware `recorded_at`.
- `tests/unit/test_ledger.py`: a balanced BUY-with-fee transaction is accepted; an unbalanced
  posting is rejected; same-magnitude postings in *different* currencies are still rejected
  (proves units never mix); zero-amount postings and single-posting transactions are rejected;
  naive datetimes are rejected.
- `tests/property/test_ledger_invariants.py`: Hypothesis generates arbitrary multi-currency,
  multi-leg posting sets that are always balanced by construction and confirms they always
  validate (RISK.md's own property-test list: "sums of postings balance per currency"); a second
  property adds one extra, deliberately unbalancing leg to a random currency and confirms
  construction always fails, across the generated input space.

Explicitly not built in Slice 3: no persistence, no builder that turns a `Fill` (Slice 2) into a
`LedgerTransaction` automatically (that mapping — which accounts a given fill's cash/position/fee
legs actually hit — belongs to the execution/reconciliation service Slices 4-6 that will also need
Postgres), no position-lot or PnL calculation, no reversal/correction transactions.

## Delivered: Slice 4 — real PostgreSQL schema + migration + `UnitOfWork`

- `migrations/versions/0002_execution.py` (`down_revision = "0001_foundation"`) + matching ORM
  rows in `wallybot/infrastructure/models.py`: `order_intents`, `order_transitions`, `fills`,
  `ledger_accounts`, `ledger_transactions`, `ledger_postings` — mirrors Slices 1-3's value types
  exactly, plus an `order_transitions` audit table (ADR-008 needs SUBMITTING, and every other
  transition, persisted before/after calling an exchange). Two dedup unique constraints straight
  from DATA.md's own wording: `order_intents(account_id, environment, idempotency_key)` and
  `fills(venue, account_id, environment, fill_id)`. `ledger_transactions(account_id,
  reference_id)` is this schema's own analogous dedup key (one transaction per fill, say). Money/
  price/quantity columns are unconstrained `NUMERIC` (arbitrary precision, DATA.md: "reject
  overflow rather than truncate"); all timestamps are `TIMESTAMPTZ`. Grants: only `wally_worker`
  gets write access — the API process stays read-only here until a dashboard slice actually needs
  orders/positions, matching least-privilege ("separate DB users and grants for migrations, API,
  trading, scheduling and research").
- `wallybot/infrastructure/unit_of_work.py`: `UnitOfWork` (save_order_intent, update_order_status,
  save_fill, save_ledger_transaction — get-or-create for `LedgerAccount` rows so the same account
  is never duplicated) plus a `unit_of_work(sessions)` async context manager built on this
  codebase's existing `sessions.begin()` idiom (auto-commit on clean exit, rollback on exception).
  This is purely a persistence primitive — it does not call any exchange or orchestrate the order
  lifecycle; that orchestration is Slice 5's `ExecutionService`.
- `tests/integration/test_execution_persistence.py` (Testcontainers, real Postgres): order-intent
  round-trip + a recorded transition, both dedup unique constraints raising `IntegrityError` on a
  duplicate, and a ledger-transaction round-trip that creates its accounts and balanced postings.
  Needed a Windows-specific `event_loop_policy` fixture (psycopg's async driver rejects the default
  ProactorEventLoop) since, unlike every other integration test, these talk to the database
  directly rather than through `TestClient`'s own selector loop.
- **Real bug found and fixed along the way:** `apps/api/main.py`'s `/health/ready` hardcodes the
  expected Alembic head revision string (`"0001_foundation"`); adding this migration silently broke
  it (readiness started returning 503) until bumped to `"0002_execution"`. Left an inline comment
  flagging this as a rough edge — resolving the head dynamically via alembic's `ScriptDirectory` is
  a real improvement but was out of scope for a migration that just needed the string bumped.

Explicitly not built in Slice 4: no `ExecutionService` wiring `OrderIntent`'s state machine,
`ExchangeGateway` and this `UnitOfWork` together; no reservations/position_lots/portfolio_snapshots/
reconciliations tables (DATA.md names these, but nothing in Slices 1-3 produces that data yet); no
outbox table (Slice 5's territory per `ARCHITECTURE.md`'s decision flow); no dashboard/API routes
reading any of this back.

## Delivered: Slice 5 — `ExecutionService`

- `wallybot/application/execution_service.py`: `ExecutionService.submit(intent)` durably claims an
  already-`VALIDATED` `OrderIntent` — persists it, commits a `SUBMITTING` transition, **then**
  calls the gateway, never holding a transaction open across the network call
  (`ARCHITECTURE.md`'s decision flow). Crash-safety comes from one rule: `submit()` never calls
  `gateway.submit_order` for an intent it finds anywhere past `VALIDATED` — it just returns the
  status already recorded. Concretely: resuming after a crash *before* the `SUBMITTING` commit
  finds `VALIDATED` and proceeds exactly like a first attempt (safe, nothing happened yet);
  resuming *after* it finds `SUBMITTING` and returns immediately without touching the exchange —
  the only way forward from there is `reconcile()`. A submission answered `UNKNOWN` is left at
  `UNKNOWN`; `submit()` does not retry it.
  `reconcile(intent)` is ADR-008's reconcile-before-retry, and the only method allowed to move an
  order out of ambiguity: finding `SUBMITTING` first transitions it to `UNKNOWN` (the diagram's own
  "Timeout or crash" edge — resuming into `SUBMITTING` *is* that ambiguity), then asks
  `gateway.lookup_order` what it actually knows. A `NOT_FOUND` answer from `UNKNOWN` is the
  diagram's "Proven absent and safe retry after risk" — the only case it's safe to move back to
  `VALIDATED`; any other observed status transitions forward through `can_transition`, raising
  `InvalidOrderTransition` rather than silently accepting an impossible jump a gateway
  shouldn't be able to report. Fills are looked up and persisted through `UnitOfWork.fill_exists`
  first, so repeated `reconcile()` calls never double-post a fill or its ledger transaction.
- `wallybot/application/ledger_postings.py`: `build_fill_ledger_transaction(fill, account_id)` —
  the `Fill → LedgerTransaction` mapping Slice 3 explicitly deferred. Two currencies' worth of
  balanced legs per fill: the account's own cash/position moves, offset by a `CLEARING` account per
  currency (DATA.md: "balanced BTC entries and balanced USD entries with clearing accounts").
  Fee is netted into the cash leg rather than given its own posting — `fills.fee` already records
  it for cost reporting, so a separate ledger leg has no consumer yet. A fee charged in a currency
  other than the instrument's quote raises rather than being silently mis-booked; no such case
  exists in this codebase yet (`FakeExchange` always charges quote-currency fees).
- `wallybot/infrastructure/unit_of_work.py` gained `get_order_status` and `fill_exists` to support
  the above without `ExecutionService` importing ORM row classes directly — it only ever composes
  `ExchangeGateway` (a port) and `UnitOfWork` (Slice 4's persistence primitive).
- `tests/unit/test_ledger_postings.py`: buy/sell leg signs and balance, non-quote fee rejection.
- `tests/integration/test_execution_service.py` (Testcontainers, real Postgres) — exactly this
  slice's stated acceptance evidence: a full market-order happy path with the expected transition
  sequence and one balanced 4-posting ledger transaction; a rejected submission that `submit()`
  never re-attempts; an `UNKNOWN` submission that stays `UNKNOWN` until `reconcile()` resolves it to
  `FILLED`; `reconcile()` called twice never double-posts; **crash before the `SUBMITTING`
  commit** (resuming from a freshly-persisted `VALIDATED` row behaves like a first attempt) and
  **crash after it** (resuming from a pre-seeded `SUBMITTING` row never re-calls the gateway, and
  `reconcile()` correctly resolves the gateway's genuine `NOT_FOUND` back to `VALIDATED`); a
  scripted partial fill observed and persisted exactly once across repeated reconciliation.

Explicitly not built in Slice 5: no cancellation orchestration (moving `PARTIALLY_FILLED`/
`ACKNOWLEDGED` through `CANCEL_REQUESTED` is its own use case, not exercised here); no automatic
scheduling of `reconcile()` for orders left at `UNKNOWN` (a future scheduler/reconciliation job,
Slice 6's territory, decides when to call it — `ExecutionService` only provides the operation);
no outbox events; no risk re-validation (an intent is assumed already `VALIDATED` by the time it
reaches `submit()`).
