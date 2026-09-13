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


## Parallel Codex UI work — 2026-09-12

User assigned Claude connections/backend and Codex UI/UX. Dark palette now implemented and deployed (web only). Verified: Next production build, 2 production browser tests, 10 web environment isolation tests, frontend lint and targeted Ruff, mobile localhost smoke. No backend restart or real enrollment. Pending Markdown: docs/PENDING.md; UI handoff: .ai/HANDOFF.md. Preserve concurrent Claude changes.


## Apple HIG-inspired UI refresh — 2026-09-12

User rejected green palette. Codex replaced theme.css with semantic neutral white/gray and graphite surfaces, accessible blue actions, larger labels, system fonts, selected navigation aria-current/indicator, keyboard skip link, reduced-motion and contrast preferences. Design evidence: docs/UI-DESIGN.md. Two production E2E tests and lint passed; desktop clear/dark and mobile screenshots inspected. Only web service rebuilt; preserve Claude backend changes.

## Kraken lookahead fix + Markets screen delivered end-to-end — 2026-09-13

**Kraken fix:** live testing against real Kraken inside the `wallybot-api` container surfaced a
real bug: `/0/public/OHLC` always returns the still-open candle as its last row, tripping
`LookaheadError`. Fixed in `wallybot/exchanges/kraken.py` by filtering with Kraken's own `"last"`
closed-candle cursor plus a `close_time > now` wall-clock check; updated
`tests/contract/test_kraken_exchange.py`'s fixture clock/assertions to match (4 real closed
candles in the recorded fixture, not 5). Full suite green (197→199), ruff/pyright clean, rebuilt
and redeployed `wallybot-api`, re-verified against live Kraken inside the container (no error, both
instruments scored/ranked). Committed as `58eb865`.

**Markets screen:** user said "no veo tanto avances en la ui" — everything through this point was
backend-only, nothing visible. Per `docs/PENDING.md`'s own P0 ("Conectar datos → calidad → scanner
→ API → pantalla de mercados"), wired the already-working `/api/markets` endpoint into an actual
frontend page: `apps/web/src/lib/dto.ts` (`marketRowSchema`/`marketsSchema`),
`apps/web/src/hooks/useMarketsData.ts`, `apps/web/src/components/dashboard/pages/MarketsPage.tsx`
(table: rank/instrument/bid/ask/spread/quality pill/score/eligibility, loading/error/empty states),
wired into `Dashboard.tsx` and a new "Mercados" nav entry in `DashboardShell.tsx` (between
Portfolio and Research, matching `ARCHITECTURE.md`'s stated nav order). Added English strings to
`lib/locales/en.json` and additive-only CSS to `theme.css` (`.markets-table`, `.quality-pill`
variants) reusing Codex's existing design tokens — did not touch Codex's in-progress dark-mode/
a11y files beyond that. Added `tests/integration/test_markets_route.py` (auth-required check +
full setup→login→`/api/markets` flow with `FakeExchange` injected via `app.state.market_overview`
override, so this mandatory test never hits live Kraken, per `TESTING.md`). Verified: `next build`,
`tsc --noEmit`, `eslint` all clean; full pytest suite 199 passed; rebuilt/redeployed `web`
container; loaded the login page live in a browser with no console errors. **Not verified in an
authenticated browser session** — no login credentials available and none were fabricated/read
from `.secrets`; the integration test is the strongest available proof the route+DTO+auth contract
actually matches what the frontend expects. Not yet committed.

**Phase 4 Slice 2 delivered** (`ExchangeGateway` port + `FakeExchange` paper execution) — see
`docs/PHASE_4.md`'s "Delivered: Slice 2" section for the full design. Summary:
`wallybot/domain/execution.py` (pure port + `SubmissionResult`/`OrderLookup`/`CancelResult`/`Fill`
value types, keyed by `client_order_id` per DATA.md so accept-then-timeout ambiguity is resolvable
via lookup without a venue order ID); `wallybot/exchanges/fake.py` extended to implement it
(balances, fee rate, scripted submission/cancel/fill outcomes, unscripted MARKET fills
immediately/fully, unscripted LIMIT never auto-fills). New tests:
`tests/contract/exchange_gateway_suite.py` + `tests/contract/test_fake_exchange_gateway.py`
(submit-then-lookup round-trip, cancel races, accept-then-timeout — this slice's stated acceptance
evidence) and `tests/unit/test_fake_exchange_execution.py` (rejections, settlement, partial fills,
partial-fill-vs-cancel race, unknown-ID safety). Verified: full suite 213 passed (199→213), ruff
and pyright clean on every touched file, domain purity confirmed
(`wallybot/domain/execution.py` imports only stdlib + `wallybot.domain.market`/`wallybot.domain.
order`). Committed as `770494e`.

**Phase 4 Slice 3 delivered** (balanced double-entry ledger value types) — see `docs/PHASE_4.md`'s
"Delivered: Slice 3". `wallybot/domain/ledger.py`: `LedgerAccount`/`LedgerPosting` (signed Decimal
amounts)/`LedgerTransaction`, enforcing DATA.md's "debit/credit equality per asset/currency" as
"signed amounts sum to zero per currency" and rejecting cross-currency cancellation ("never mix
units"). `tests/unit/test_ledger.py` + `tests/property/test_ledger_invariants.py` (Hypothesis:
arbitrary balanced multi-currency posting sets always validate; any single unbalancing leg always
fails). Verified: full suite 222 passed (213→222), ruff/pyright clean, domain purity confirmed
(stdlib only). Committed as `0135a13`.

**Phase 4 Slice 4 delivered** (real PostgreSQL schema + migration + `UnitOfWork`) — see
`docs/PHASE_4.md`'s "Delivered: Slice 4". `migrations/versions/0002_execution.py` +
`wallybot/infrastructure/models.py` ORM rows for order_intents/order_transitions/fills/
ledger_accounts/ledger_transactions/ledger_postings, with DATA.md's two named dedup unique
constraints. `wallybot/infrastructure/unit_of_work.py`: `UnitOfWork` + `unit_of_work()` context
manager, pure persistence primitive (no orchestration — that's Slice 5). Found and fixed a real
bug along the way: `apps/api/main.py`'s `/health/ready` hardcoded the Alembic head revision string,
so this migration silently broke readiness (503) until bumped — left an inline comment flagging
it as a known rough edge for a future dynamic fix. `tests/integration/test_execution_persistence.py`
(Testcontainers/real Postgres) covers round-trips and both dedup constraints. Verified: full suite
227 passed (222→227), ruff/pyright clean. Committed as `3f222b3`.

**Phase 4 Slice 5 delivered** (`ExecutionService`) — see `docs/PHASE_4.md`'s "Delivered: Slice 5".
`wallybot/application/execution_service.py`: `submit()` durably claims a `VALIDATED` intent
(persist → commit `SUBMITTING` → *then* call the gateway, never holding a transaction across the
network call) and never re-calls the gateway for anything already past `VALIDATED` — that single
rule gives crash-safety for both "crash before the `SUBMITTING` commit" (resumes as a fresh
attempt) and "crash after it" (resumes and waits for `reconcile()`, never re-submits).
`reconcile()` is ADR-008's reconcile-before-retry: `SUBMITTING` found on resume first moves to
`UNKNOWN` (the diagram's own "Timeout or crash" edge), then a gateway lookup either proves the
order absent (safe retry back to `VALIDATED`) or resolves it forward via `can_transition`
(raising `InvalidOrderTransition` on an impossible jump rather than accepting it). Fills are
deduped via `UnitOfWork.fill_exists` before ever posting a ledger transaction.
`wallybot/application/ledger_postings.py`: `build_fill_ledger_transaction` — the `Fill →
LedgerTransaction` mapping Slice 3 deferred (cash/position legs offset by a `CLEARING` account per
currency; fee netted into cash, not its own leg; non-quote fee currency raises rather than
mis-booking). `UnitOfWork` gained `get_order_status`/`fill_exists` so `ExecutionService` never
imports ORM rows directly — it only composes `ExchangeGateway` and `UnitOfWork`. Found and fixed a
real design gap while writing the crash tests: `reconcile()` initially only accepted `NOT_FOUND`
from `UNKNOWN`, but a crash-after-`SUBMITTING` resume legitimately finds `SUBMITTING` with a
genuinely-never-called gateway — fixed by having `reconcile()` move `SUBMITTING` to `UNKNOWN`
first, exactly matching the lifecycle diagram's own edge, before resolving further.
`tests/integration/test_execution_service.py` (Testcontainers) covers this slice's full stated
acceptance evidence: happy path with the exact expected transition sequence, rejected submission
never re-attempted, `UNKNOWN` resolved only via `reconcile()`, repeated `reconcile()` never
double-posts, both crash scenarios, and a scripted partial fill observed exactly once. Verified:
full suite 237 passed (227→237), ruff/pyright clean. Committed as `b3faee0`.

**Phase 4 Slice 6 delivered** (reconciliation sweep) — see `docs/PHASE_4.md`'s "Delivered: Slice
6". `wallybot/application/reconciliation_service.py`: `ReconciliationService.sweep(environment)`
calls `ExecutionService.reconcile_order` across every non-terminal order in Postgres, catching one
order's failure as its own `ReconciliationOutcome` rather than aborting the sweep. Refactored
`ExecutionService.reconcile`/`_observe` to work off plain `(client_order_id, venue, account_id,
environment)` instead of requiring a full `OrderIntent` — that was always all they used, and it's
what makes a sweep possible at all (Postgres never stored full `Instrument` fidelity, so a sweep
reading rows back could never reconstruct one). `reconcile(intent)` still works unchanged for the
common case; `reconcile_order(...)` is the new sweep-facing entry point.
`UnitOfWork.list_open_order_intents(environment)` is the one new read. Verified: full suite 240
passed (237→240), ruff/pyright clean. Not yet committed.

**Phase 4 status: all 6 slices done — Phase 4 is complete as `docs/PHASE_4.md`'s backlog scoped
it.** Explicitly still missing (each flagged in the relevant slice's "Delivered" section, not a
surprise): cancellation orchestration, position-lot/PnL, real balance reconciliation against a
venue, an outbox, a scheduler actually calling `sweep()` periodically, and any dashboard/API
surface reading order/fill/ledger state back. Per `docs/PENDING.md`'s own recommended delivery
order ("mercado visible y calidad → decisión persistida → PAPER con ledger y recuperación →
evaluación reproducible → ..."), the natural next major body of work is either (a) wiring Phase
3's `RiskEngine`/`PortfolioAllocator` output into an actual persisted "decision" that becomes the
`OrderIntent` this phase's `ExecutionService` consumes — closing the gap between "signals exist"
and "PAPER trades actually happen end-to-end" — or (b) more UI-facing work, since everything in
Phase 4 is still backend-only and invisible, same category of gap the Markets screen fixed for
Phase 2. Given this session's history (the user's last UI-visibility complaint), (b) may be the
more valuable next move once Phase 4's backend is committed, but the connecting-decision-to-intent
work in (a) is what actually makes a first real PAPER trade possible at all.

**Decision pipeline delivered** — user explicitly chose "conectar el pipeline de decisión" when
asked. See `docs/DECISION_PIPELINE.md` for full detail. Summary:
`wallybot/application/decision_pipeline.py`'s `DecisionPipeline.run()` composes, for the first
time, `scan_universe` (Phase 2) → quality gate → `classify_regime`/`Strategy`/`SignalAggregator`/
`PortfolioAllocator`/`RiskEngine` (Phase 3) → `OrderIntent`/`ExecutionService` (Phase 4) into one
real, tested, closed loop from market data to a submitted order. `wallybot/infrastructure/
uuid_id_generator.py` (`UuidIdGenerator`) is the first concrete `IdGenerator`. Found and fixed a
real gap while wiring this (separate commit `fe8b403`): `RiskAssessment` only carried
`final_notional`, not the `final_quantity` RISK.md's own contract calls for — needed to actually
build an `OrderIntent`. `tests/integration/test_decision_pipeline.py` (Testcontainers): a
hand-built uptrend series produces a real FILLED order with a balanced ledger transaction end to
end; a bucket at its ceiling and an active risk breaker both correctly produce no order. Verified:
full suite 243 passed (240→243, plus the risk fix commit already included), ruff/pyright clean.
Not yet committed (this pipeline itself; the risk fix is already committed).

Explicitly still missing, flagged in `docs/DECISION_PIPELINE.md`: no equity/PnL/breaker tracker
feeding real `PortfolioState`/`RiskEnvironment` inputs (a caller still has to supply these), no
persisted `decisions` record (only the resulting `OrderIntent` is durable — a HOLD/REJECTED
outcome today only lives in the returned `DecisionOutcome`, not in Postgres), no scheduling.

## Architecture/objective expansion + Phase 10 kickoff — 2026-09-13

User provided a large target-architecture spec (wallet/entity intelligence, Smart Money scoring/
clustering, on-chain/whale/disclosure signals, an AI strategy layer producing `TradeProposal`s,
OBSERVE/PAPER/SHADOW/LIVE per-strategy execution modes) and asked for it in the architecture and
objective docs. Folded into `README.md` (objective) and `ARCHITECTURE.md` (new provider ports,
"Multi-source intelligence and Smart Money" section, "AI strategy layer and TradeProposal"
section reconciled against the *existing* decision flow rather than describing a competing one,
portfolio-buckets naming note flagging Core/Tactical vs. shipped Core/Growth as a real open item,
Phases 10-15 added to the implementation sequence). Documentation only, committed as `b1a2809`.

User then said "continua con todo" — started Phase 10 ("Wallet/entity intelligence
infrastructure ... OBSERVE mode only, no execution authority"), the lowest-risk starting point
per its own description. See `docs/PHASE_10.md`. Delivered Slices 1-2:
`wallybot/domain/entity.py` (`Entity`/`Attribution`/`EntityType`/`VerificationStatus`, provenance
mandatory by construction) and `wallybot/domain/wallet.py` (`Wallet`/`WalletCluster`/
`MonitoringMode`, defaults to `OBSERVE`); `wallybot/domain/validation.py` factored out shared
aware-datetime/unit-interval checks. `migrations/versions/0003_intelligence.py` +
`EntityRepository`/`WalletRepository` (upsert summary fields, append-only attributions deduped by
`(parent, source, source_entity_id, observed_at)`, insert-only wallet clusters). Bumped
`apps/api/main.py`'s hardcoded Alembic revision check again (same recurring rough edge as Phase 4
Slice 4) to `"0003_intelligence"`. Verified: full suite 271 passed (243→265→271), ruff/pyright
clean, domain purity confirmed, migration applied and verified against the live `wallybot-api`
container. Committed as `b7e22dc`.

**Phase 10 Slice 3 delivered** (Entity Correlation Graph) — see `docs/PHASE_10.md`'s "Delivered:
Slice 3". `wallybot/domain/relationship.py`: `NodeReference`/`NodeReferenceType`/
`RelationshipType` (all 12 spec'd types)/`Relationship` — a flat generic edge reusing `Attribution`
directly rather than a second provenance shape; `Company`/`Person`/`Fund`/`Exchange` all collapse
to `ENTITY` (already distinguished by `Entity.entity_type`). `migrations/versions/
0004_relationships.py` + `RelationshipRow` (one table, attribution fields embedded, no join
table) + `RelationshipRepository` (insert-only `save`, `get`, one-hop `find_by_node`). Bumped
`apps/api/main.py`'s hardcoded Alembic revision check again to `"0004_relationships"` (same
recurring rough edge, still not fixed dynamically). Verified: full suite 281 passed
(271→281), ruff/pyright clean, domain purity confirmed, migration applied and verified against
the live `wallybot-api` container. Not yet committed.

**Phase 10 Slice 4 delivered (port + fake only)** — see `docs/PHASE_10.md`'s "Delivered: Slice 4".
`wallybot/domain/wallet_activity.py`: `OnChainActionType` (all 12 spec'd), `WalletActivityEvent`
(normalized observation, amount always positive, direction lives in `action`),
`WalletIntelligenceProvider` port. `wallybot/intelligence/fake.py` (new capability package):
`FakeWalletIntelligenceProvider` — returns only what it's seeded with, no random generator, since
no real provider exists yet to imitate. Contract suite + test module mirror the established
Kraken/FakeExchange pattern. Verified: full suite 297 passed (281→297), ruff/pyright clean,
domain purity confirmed. Not yet committed.

**Blocked: Slice 4b (a real wallet/entity vendor adapter — Arkham/Nansen/Helius/Birdeye/Whale
Alert/Dune/...).** Every one of these needs an API key this session does not have (unlike
Kraken's public market-data endpoints, verified credential-free in Phase 2). Asked the user which
provider they had access to.

**Phase 10 Slice 4c delivered** (user confirmed CoinGecko access). `wallybot/domain/
market_metadata.py`: `TokenMarketMetadata`/`MarketMetadataProvider` — a port ARCHITECTURE.md's
Contracts table already named as planned. `wallybot/market/coingecko.py`:
`CoinGeckoMarketMetadataProvider`, same injectable-transport shape as `KrakenExchange`. Verified
CoinGecko's `/coins/markets` needs no API key at all (checked live via `curl` first, same as
Kraken). `tests/contract/test_coingecko.py` uses a real recorded response fixture; also verified
directly against the live API (real bitcoin/ethereum data, Ethereum's absent `max_supply`
correctly `None`, not a fabricated `0`). Verified: full suite 314 passed (297→314), ruff/pyright
clean, domain purity confirmed. Not yet committed.

**Phase 10 Slice 5 delivered** (on-chain event ingestion, polling-based) — see `docs/PHASE_10.md`'s
"Delivered: Slice 5". New `wallet_activity_events` table (FK'd to `wallets`, deduped on
`(chain, address, transaction_hash, token, action)`), `WalletActivityRepository`,
`WalletRepository.list_enabled_wallets()`, and `wallybot/application/wallet_monitoring_service.py`'s
`WalletMonitoringService` (`sync_wallet`/`sync_all_enabled_wallets`, same per-item failure-isolation
shape as `ReconciliationService`). Docker Desktop had stopped mid-session (needed to be relaunched
and the full `docker compose up -d` stack brought back before verification could continue — noted
here since it briefly blocked all Testcontainers-based integration tests, not just this slice's).
Verified: full suite 317 passed (314→317), ruff/pyright clean, migration applied and verified
against the live `wallybot-api` container. Not yet committed.

**Phase 10 status: Slices 1-5 delivered.** Remaining backlog: Slice 4b (blocked on a real
wallet/entity vendor API key).

**Phase 11 Slice 1 delivered** (Smart Money scoring engine) — see `docs/PHASE_11.md`. The wider
spec names ~20 scoring dimensions; this codebase's `WalletActivityEvent` log only supports five of
them (realized PnL, win rate, trade count, wallet age, holding period), so
`wallybot/domain/smart_money.py`'s `score_smart_money` scores only those and lists the other
fifteen, by name, as "not evaluated" in every snapshot's `reasons` rather than faking a complete
picture. A wallet under `MIN_COMPLETED_TRADES` (5) realized round trips (FIFO-matched BUY/SELL
pairs, reusing DATA.md's own convention) gets `INSUFFICIENT_DATA` and no score at all — structural
enforcement of "never classify a wallet as Smart Money merely because it had one profitable
trade." The 60/40 win-rate/PnL scoring weights are an explicitly-labeled versioned placeholder,
not a calibration — nothing consumes this score for any financial decision yet.
`SmartMoneyScoreSnapshotRow`/`migrations/versions/0006_smart_money.py`/
`SmartMoneyScoreRepository` are insert-only: no unique constraint on `wallet_id` at all, so a
fresh evaluation is always a new row, never an update ("store the score history... never
overwrite previous score snapshots"). Verified: full suite 331 passed (317→331), ruff/pyright
clean, domain purity confirmed, migration applied and verified against the live `wallybot-api`
container. Not yet committed.

**Phase 11 Slice 2 delivered** (Smart Money clustering) — see `docs/PHASE_11.md`'s "Delivered:
Slice 2". `wallybot/domain/smart_money_cluster.py`: `SmartMoneyClusterSignal` (immutable,
self-validating) + `detect_smart_money_clusters(events_by_wallet, entity_by_wallet, action, window,
min_independent_wallets=3)` — a documented single left-to-right sweep per `(chain, token)` market
that fires a signal when enough *independent* wallets (wallets sharing a known `entity_id` collapse
to one participant) act on the same token within the window, jumping past every consumed event so
no wallet is ever claimed by two signals. Same "honest partial evaluation" principle as Slice 1:
liquidity/volume/holder change, price movement and market regime are named, by dimension, as "not
evaluated" in every signal's `reasons` rather than folded into a fabricated confidence number.
`SmartMoneyClusterSignalRow`/`migrations/versions/0007_smart_money_clusters.py`/
`SmartMoneyClusterRepository` follow the exact insert-only pattern as Slice 1's score snapshots.
Bumped `apps/api/main.py`'s hardcoded Alembic revision check again to
`"0007_smart_money_clusters"` (same recurring rough edge, still not fixed dynamically). Verified:
full suite 346 passed (331→346), ruff clean, pyright clean on every new/changed file (a
pre-existing, unrelated pyright backlog in `test_security.py`/`auth_routes.py`/`system_routes.py`/
`tests/integration/conftest.py` predates this slice), domain purity confirmed, migration applied
and verified against the live `wallybot-api` container (head `0007_smart_money_clusters`,
`/health/ready` → `ready`). Not yet committed.

**Phase 11 Slice 3 delivered** (token intelligence / `TokenRiskScore`) — see `docs/PHASE_11.md`'s
"Delivered: Slice 3". `wallybot/domain/token_risk.py`: `SecurityAnalysisResult`/
`SecurityAnalysisProvider` port + `score_token_risk` — scores only mint/freeze authority,
liquidity-lock, buy/sell tax, honeypot and malicious labels (every field the provider actually
reported); holder concentration and contract/pool/developer-wallet age are named `UNSCORED_
DIMENSIONS` since no provider models them. Higher `risk_score` (0-100) means riskier — opposite
polarity from Smart Money's score, since this gates entry. A honeypot or malicious label always
forces 100 regardless of other clean checks. No real `SecurityAnalysisProvider` vendor (GoPlus/
Honeypot.is/TokenSniffer/RugCheck) is integrated — same "blocked on a vendor API key" situation as
Phase 10 Slice 4b — so this is port + pure scoring + `FakeSecurityAnalysisProvider` only, same
shape as Slice 4's wallet-intelligence delivery. `TokenRiskScoreRow`/`migrations/versions/
0008_token_risk.py`/`TokenRiskScoreRepository` are insert-only, same pattern as Slices 1-2. Bumped
`apps/api/main.py`'s hardcoded Alembic revision check again to `"0008_token_risk"`. Verified: full
suite 368 passed (346→368), ruff/pyright clean (pre-existing unrelated pyright backlog in
`test_security.py`/`auth_routes.py`/`system_routes.py`/`tests/integration/conftest.py` untouched),
domain purity confirmed, migration applied and verified against the live `wallybot-api` container
(head `0008_token_risk`, `/health/ready` → `ready`). Committed as `a36c8fb` (Slice 2); Slice 3 not
yet committed.

**Phase 11 Slice 4 delivered** (whale intelligence, large-transfer half only) — see
`docs/PHASE_11.md`'s "Delivered: Slice 4". `wallybot/domain/whale_flow.py`:
`WhaleTransferSignal` + `detect_whale_transfers(events, threshold_usd)` — flags any
`WalletActivityEvent` whose `value_usd` meets/exceeds the threshold, skipping unpriced events
rather than treating them as zero. Exchange/stablecoin flow-direction classification (the other
half ARCHITECTURE.md names) is explicitly NOT built: `WalletActivityEvent` has no counterparty/
destination-wallet field at all, so there's no data to classify a transfer as exchange-related —
a real schema gap, not an API-key blocker, flagged as future work (extending `WalletActivityEvent`
itself). `WhaleTransferSignalRow`/`migrations/versions/0009_whale_transfers.py`/
`WhaleTransferRepository` follow the same insert-only pattern as Slices 1-3. Bumped
`apps/api/main.py`'s hardcoded Alembic revision check again to `"0009_whale_transfers"`. Verified:
full suite 380 passed (368→380), ruff/pyright clean, domain purity confirmed, migration applied
and verified against the live `wallybot-api` container (head `0009_whale_transfers`,
`/health/ready` → `ready`). Not yet committed.

**Phase 11 Slice 5 delivered** (provider reliability + price consensus) — see `docs/PHASE_11.md`'s
"Delivered: Slice 5". `wallybot/domain/provider_reliability.py`: `ProviderCallOutcome` +
`compute_provider_reliability(provider, outcomes, now)` — HEALTHY/DEGRADED/UNRELIABLE/
INSUFFICIENT_DATA from error rate/latency thresholds, fewer than 5 calls yields INSUFFICIENT_DATA,
no success at all always forces UNRELIABLE. `wallybot/domain/price_consensus.py`: `PriceQuote` +
`compute_price_consensus(instrument_id, quotes, now, max_staleness, outlier_threshold_pct)` —
drops stale quotes before computing at all, excludes median-outliers, needs ≥2 surviving quotes or
yields INSUFFICIENT_DATA. Both are pure functions tested against synthetic inputs since this
codebase still has only one real provider per data kind (no live multi-provider overlap exists yet
to compute a genuine consensus from). Neither wires into the existing `wallybot/risk/` breaker
mechanism or any real adapter's call path — that instrumentation is separate future work.
Persistence (`ProviderReliabilitySnapshotRow`/`PriceConsensusResultRow` + migration
`0010_provider_reliability_and_price_consensus.py` + two repositories) follows the same
insert-only pattern as Slices 1-4. Bumped `apps/api/main.py`'s hardcoded Alembic revision check
again to `"0010_provider_reliability"`. Verified: full suite 412 passed (380→412), ruff/pyright
clean, domain purity confirmed, migration applied and verified against the live `wallybot-api`
container (head `0010_provider_reliability`, `/health/ready` → `ready`). Not yet committed.

**Phase 11 status: complete — Slices 1-5 all delivered.** Real, tracked open items across the
whole phase (each named explicitly in its own slice's `reasons`/`UNSCORED_DIMENSIONS`/
`UNEVALUATED_DIMENSIONS`, never silently declared done): Slice 4b's real wallet/entity vendor
adapter, Slice 3's real `SecurityAnalysisProvider` adapter, Slice 4's exchange-flow classification
(needs a `WalletActivityEvent` schema extension), and Slice 5's circuit-breaker wiring/real
multi-provider data/rate-limit-outage detection. Per ARCHITECTURE.md's implementation sequence,
Phase 12+ (AI strategy layer/`TradeProposal`, political/financial disclosure ingestion, or wiring
any of Phase 10/11's OBSERVE-only signals into the actual decision pipeline) is the natural next
body of work — none started, each needs its own design pass.

## Phase 12 kickoff (AI strategy engine / TradeProposal) — 2026-09-13

User said "continua con las phases"; picked Phase 12 per ARCHITECTURE.md's implementation
sequence ("AI strategy engine producing schema-validated TradeProposals, wired into the existing
RiskEngine/PortfolioAllocator/ExecutionService pipeline; SHADOW mode before any LIVE
eligibility"). Full slice plan in `docs/PHASE_12.md`.

**Phase 12 Slice 1 delivered** (`TradeProposal` domain type + `AIProvider` port, pure, no
persistence, no wiring) — see `docs/PHASE_12.md`'s "Delivered: Slice 1". `wallybot/domain/
trade_proposal.py`: `TradeDirection`, `AIAnalysisContext` (same validated inputs `Strategy.
evaluate` already consumes: instrument/features/regime/strategy signals), `TradeProposal` (every
field ARCHITECTURE.md's Contracts entry names: direction, strategy, confidence, suggested
allocation/entry/stop/take-profit, time horizon, signal TTL, reasons, risks, supporting signal
IDs, invalidating conditions, source event IDs, model ID, prompt version) with `__post_init__`
enforcing stop/take-profit ordering is correct for the given direction, all the usual range/
positivity/non-empty-evidence checks. `AIProvider.analyze(context) -> TradeProposal | None` is
async (like `WalletIntelligenceProvider`/`SecurityAnalysisProvider` — a real adapter makes a
network call) and returns `None`, never a fabricated proposal, when the model has nothing
actionable — callers must treat that as HOLD per RISK.md. `wallybot/intelligence/fake_ai.py`:
`FakeAIProvider`, same seeded-fake pattern as the other intelligence fakes, no real LLM call.
Verified: `uv run pytest tests/unit tests/property -q` → 341 passed (no persistence yet, so no
integration/contract tests needed for this slice, same as Phase 4 Slice 1's pure-domain pattern).
ruff/ruff-format/pyright clean on every new file, domain purity confirmed (imports only stdlib +
existing domain modules).

**Explicitly not built this slice** (see `docs/PHASE_12.md` for the full remaining backlog):
persistence/audit trail (Slice 2), any wiring into `RiskEngine`/`PortfolioAllocator`/
`ExecutionService`/`DecisionPipeline` (Slice 3, gated behind SHADOW mode — a `TradeProposal` today
has zero ability to affect anything running), the typed read-only AI tool surface ARCHITECTURE.md
names, any real model adapter or cost/budget accounting (Phase 6 was never built), and `SHADOW` as
an actual mode value anywhere in the codebase.

**Phase 12 Slice 2 delivered** (insert-only persistence/audit trail) — see `docs/PHASE_12.md`'s
"Delivered: Slice 2". `migrations/versions/0011_trade_proposals.py` + `TradeProposalRow` +
`wallybot/infrastructure/trade_proposal_repository.py`'s `TradeProposalRepository` —
**write-only by design**: reconstructing a full `TradeProposal` from a row would need a fabricated
`Instrument` (price/quantity increments were never persisted), the same reason `OrderIntentRow`/
`PriceConsensusResultRow` never round-trip a full `Instrument` either. A future read consumer
defines its own shape against the real columns instead. Bumped `apps/api/main.py`'s hardcoded
Alembic revision check to `"0011_trade_proposals"` (same recurring rough edge). Verified: full
suite 438 passed (341→438), ruff/pyright clean, migration applied and verified against the live
`wallybot-api` container (rebuilt, redeployed, `/health/ready` → `ready`). Committed.

**Codex parallel UI task:** launched `codex exec --approve-for-me` in the background (after the
user approved a `.claude/settings.local.json` permission rule for `Bash(codex exec*)`, gitignored)
to finish/commit its own already-uncommitted UI work. It hit its own ChatGPT usage limit mid-task
(not a Claude Code permission issue) before reaching its commit step — its work stayed uncommitted
but intact in the tree (nothing lost). User then said they weren't seeing progress and to "hazlas"
(actually do them) — Claude verified (tsc/eslint/next build/full Playwright suite, all green) and
committed Codex's pending UI work directly (`9e812da`): markets filters, grouped system panel,
richer activity search, and a real dev.py bug fix (the web process was mislabeled "api" and given
full backend credentials; now isolated to `WALLY_DEV_API` only).

**Smart Money UI connected end-to-end** (2026-09-13) — the first Phase 10/11 intelligence
capability made visible in the product, closing the "backend exists, nothing shows it" gap
`docs/PENDING.md` flags. `wallybot/infrastructure/smart_money_repository.py` gained `list_latest()`
(Postgres `DISTINCT ON` per wallet, newest-first) — the Smart Money repository previously only
supported per-wallet `latest`/`history`, no cross-wallet listing. `apps/api/intelligence_routes.py`
(`GET /api/intelligence/smart-money`, `SignedIn`-gated) + `apps/api/dto.py`'s
`SmartMoneyRowView`/`SmartMoneyView`. **Found and fixed a real access-control gap while wiring
this**: `wally_api` had never been granted `SELECT` on `smart_money_score_snapshots` (only
`wally_worker`, which writes it, had any grant) — added `migrations/versions/
0012_smart_money_api_grant.py` rather than widen the role's grants generically. Bumped
`apps/api/main.py`'s hardcoded Alembic revision check to `"0012_smart_money_api_grant"` (same
recurring rough edge). Frontend: `apps/web/src/lib/dto.ts`'s `smartMoneyRowSchema`/
`smartMoneySchema`, `useSmartMoneyData.ts`, `SmartMoneyPage.tsx` (table: wallet/status/score/
trades/win-rate/PnL/reasons, loading/error/empty states, ES/EN), a new "Inteligencia" nav entry in
`DashboardShell.tsx` (between Markets and Research) and `/intelligence` route in
`app/[section]/page.tsx`. `tests/integration/test_smart_money_route.py` (auth-required + seeded
scored/insufficient-data rows via the real repository) and a new Playwright test in
`observability.spec.ts` (loading → empty → populated → error, mocked). Verified: full suite 441
passed (438→441), ruff/pyright/tsc/eslint/next-build all clean, `api` and `web` containers rebuilt
and redeployed, `/health/ready` → `ready` at the new migration head, `/login` serving 200.

**Whale flow + token risk connected to the same Inteligencia page** (2026-09-13, same session,
user said "continua sin parar... quiero mi producto terminado"). Same pattern as Smart Money:
`TokenRiskScoreRepository.list_latest()` added (DISTINCT ON per (chain, token_id) -- it previously
only had per-token `latest`/`history`); `WhaleTransferRepository.latest()` already existed, no
repo change needed. `GET /api/intelligence/whale-flow` and `GET /api/intelligence/token-risk`
added to `apps/api/intelligence_routes.py` + `dto.py`. **Same access-control gap found again**:
`wally_api` had no grant on `whale_transfer_signals`/`token_risk_scores` either --
`migrations/versions/0013_intelligence_api_grants.py` (bumped `/health/ready`'s check to
`"0013_intelligence_api_grants"`). Frontend: `WhaleFlowSection.tsx`/`TokenRiskSection.tsx` +
`IntelligencePage.tsx` (composes Smart Money + these two into one page, one "Inteligencia" nav
entry, no new routes needed). `tests/integration/test_whale_flow_route.py` +
`test_token_risk_route.py` + 2 new Playwright tests. Verified: full suite 447 passed (441→447),
ruff/pyright/tsc/eslint/next-build clean, both containers rebuilt/redeployed, `/health/ready` →
`ready`.

**Phase 12 Slice 3 delivered** (SHADOW mode) — see `docs/PHASE_12.md`'s "Delivered: Slice 3".
`wallybot/application/shadow_decision_service.py`'s `ShadowDecisionService` runs a `TradeProposal`
through the same `PortfolioAllocator`/`RiskEngine` gate `DecisionPipeline` uses, holding no
reference to `ExecutionService`/`IdGenerator` at all -- structurally incapable of submitting an
order. `ShadowDecisionRow`/migration `0014_shadow_decisions`/`ShadowDecisionRepository`
(write-only, same reasoning as `TradeProposalRepository`). The integration test's actual proof:
after a SHADOW evaluation, `order_intents` stays empty. Verified: full suite 452 passed
(447→452), ruff/pyright clean, container redeployed, `/health/ready` → `ready`.

**Phase 5 kicked off** (datasets/backtests/evaluation) — see `docs/PHASE_5.md`. Slice 1 delivered:
`wallybot/data/historical_query.py`'s `read_candles()`, a DuckDB reader over ADR-005's
already-existing checksummed Parquet manifests (written since Phase 2 Slice 5, never read back
until now). Two real bugs found and fixed via actual test execution: (1) an early draft
fabricated `Instrument.price_increment`/etc. from Parquet columns that were never written —
same mistake `TradeProposalRepository` already documents avoiding, fixed by having the caller
supply the real `Instrument`; (2) DuckDB's Python client silently converts `TIMESTAMPTZ` to the
host's local timezone on fetch — fixed with `SET TimeZone='UTC'`, caught only because the test
suite actually ran on this machine and returned Mexico-City-shifted timestamps. Added `duckdb`
and `pytz` as real dependencies. Verified: full suite 460 passed (452→460), ruff/pyright clean. Committed.

**Phase 5 Slice 2 delivered** (backtest engine) — see `docs/PHASE_5.md`'s "Delivered: Slice 2".
`wallybot/backtest/engine.py`'s `BacktestEngine`: single-instrument/single-strategy/long-only
replay reusing `FeatureEngine`/`Strategy`/`classify_regime` exactly as `DecisionPipeline` does.
Fills at the *next* candle's open (never the signal candle's own price -- would be lookahead);
`BacktestCostModel.fee_rate` defaults to `FakeExchange`'s own 0.001 so PAPER and backtests share
one fee assumption; `slippage_pct` is an explicit placeholder (no PAPER equivalent to share,
since FakeExchange simulates a real spread instead). `tests/unit/test_backtest_engine.py`: 9
tests, all passed on first run against hand-derived expected fill prices/PnL for a real
rise-then-fall series driven by the actual `TrendFollowingStrategy`. Verified: full suite 469
passed (460→469), ruff/pyright clean.

**What's realistically left for a "finished product"**: Phase 5 Slices 3-5 (walk-forward/Monte
Carlo, experiment/strategy-registry persistence, backtest UI); Phase 12 Slice 4 (real AI adapter
-- needs an authorized model/API key decision) and an orchestrator that actually calls
`ShadowDecisionService` on a schedule (none exists yet); connecting the remaining Phase 10/11
OBSERVE-only signals (wallet activity feed itself, entity correlation graph, provider
reliability/price consensus) to the UI the same way Smart Money/whale flow/token risk were;
Phases 7/8 (research agents, Telegram); and Phase 9 (LIVE trading) -- which per RISK.md/
SECURITY.md requires explicit human-authorized evidence gates and real exchange credentials and
must never be rushed to "look done." Continuing sequentially, one verified slice at a time, same
discipline as every slice above.


## Activity inspection UI — 2026-09-12

Codex continued observability UI while Claude owns market/backend integration. EventsPage adds text search (message/code/id), type filter, newest/oldest sort, refresh, explicit failure/stale states and empty filter reset. EventList detailed mode exposes stable ID, original event code and full UTC timestamp. Filters are explicitly limited to the latest 100 API events; no claim of full-history search or live stream. No API/DB changes. Verified frontend lint, Next production build and 2 production E2E tests including filters, details, ES/EN and mobile no-overflow; activity mobile screenshot inspected. Web-only deployment. Next: backend history pagination contract with Claude, translated display labels, live stream only after authenticated server delivery exists.
