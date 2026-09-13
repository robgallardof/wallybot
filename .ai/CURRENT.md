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
227 passed (222→227), ruff/pyright clean. Not yet committed.

**Next up:** Slice 5 (`ExecutionService` — durable claim, SUBMITTING before network call, UNKNOWN
resolution, reconcile-before-retry per ADR-008) is the next backlog item — the piece that actually
wires `OrderIntent`'s state machine, `ExchangeGateway` and this `UnitOfWork` together. It's the
highest-stakes piece of Phase 4 so far (failure-injection tests: crash before/after SUBMITTING,
ambiguous timeout, no duplicate fills) and deserves its own dedicated design pass, same discipline
as `RiskEngine` got in Phase 3.


## Activity inspection UI — 2026-09-12

Codex continued observability UI while Claude owns market/backend integration. EventsPage adds text search (message/code/id), type filter, newest/oldest sort, refresh, explicit failure/stale states and empty filter reset. EventList detailed mode exposes stable ID, original event code and full UTC timestamp. Filters are explicitly limited to the latest 100 API events; no claim of full-history search or live stream. No API/DB changes. Verified frontend lint, Next production build and 2 production E2E tests including filters, details, ES/EN and mobile no-overflow; activity mobile screenshot inspected. Web-only deployment. Next: backend history pagination contract with Claude, translated display labels, live stream only after authenticated server delivery exists.
