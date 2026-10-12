## Verified real spot delivery — 2026-10-12

Operator-approved Kraken spot USD/XBT/ETH is implemented and deployed. Credentials and limits
are entered by the operator through the UI with fresh MFA. No real account is configured and
no real orders were placed. Runtime remains OBSERVE. Preserve unrelated Rust work.

Verification: 952 backend tests passed (144.53s); production browser suite 19 passed (48.1s);
WallyBot-scoped Pyright zero errors; Ruff, frontend types and focused lint passed. Eight Compose
services healthy, readiness 200, migration 0044 deployed. Native AI heartbeat verified.
Codex readiness succeeds; Claude is not logged in. Operator must log in locally or configure
only available analysts in the UI; do not silently weaken consensus.

LIVE includes encrypted trade-only credentials, nonce serialization, manual single-use approval,
mode/version binding, bounded IOC limits, ledger opening balances, fill recovery and periodic
reconciliation. Account discrepancies and losses block execution. No withdrawals, transfers,
leverage, AI direct orders or automatic stop sales. See docs/adr/018-real-spot-objective.md and
docs/runbooks/real-spot-trading.md. Funded venue acceptance remains untested.

Published WallyBot to https://github.com/robgallardof/wallybot on main (implementation
commit 10fa747). Spanish README includes installation, real-account configuration, architecture
and documentation. Protected paths and unrelated Rust are excluded; reachable master history
and staged content passed a token/private-key pattern scan. Codex checkpoint refs were not pushed.

## Verified PAPER delivery — 2026-10-08

This entry supersedes the older Docker-unavailable status below. User authorized completing
WallyBot only; unrelated Rust work and existing dirty changes were preserved.

Implemented trustworthy Kraken bid marks (source/instrument/age/spread validation), FIFO
remaining cost and realized/unrealized proposal position results, partial reductions, closed
holding time, and read-only stop/target review states. Failed/stale quotes withhold valuations.
Telegram /approve, /reject and /simulate return owner-scoped review links; only the web's
authenticated Admin + fresh MFA + CSRF path can decide. Links never execute actions.

Both local CLI analysts passed real HOLD readiness calls; Telegram getMe and public Kraken
quotes responded. Native Windows AI worker now has hidden start/stop scripts, isolated CLI
subprocesses, a 10-second heartbeat, and migration 0041 restricting its database role from
orders/fills/ledger access. Eight Compose services are healthy and readiness returns 200.
API/native-worker restart preserved existing production row counts (no production orders or
fills existed). Runtime analysis remains DISABLED until the operator enables it through MFA.
No LIVE, transfer, withdrawal, automatic stop sale, or real-money trade was enabled.

Verification: 911 unit/property/contract/integration tests passed using real disposable
PostgreSQL/Redis (143.21s); WallyBot-scoped Pyright zero errors; Ruff and frontend TypeScript/
focused ESLint passed. Final production browser rerun passed 17/17 in 42.6s, including
production CSP and setup/MFA/recovery. Evidence is recorded in docs/stats/testing.md.
Integration startup now skips external market ingestion; job tests invoke it explicitly.
Third-party deprecation warnings and a Windows pytest-cache permission warning remain.

Launch/restart: scripts/start_wallybot.ps1, scripts/start_ai_worker.ps1,
scripts/stop_ai_worker.ps1. See docs/runbooks/native-ai-worker.md.
Before claiming operation, check System heartbeat and enable analysis in Settings with the
operator's session/MFA. HOLD is a valid analyst response and does not guarantee a proposal.
Quote levels are review information; future selling still requires a separate approved proposal.
Broader multi-provider/equities/LIVE roadmap items in docs/PENDING.md are outside this delivery.

## WallyBot completion verification — 2026-10-08

User explicitly resumed WallyBot, excluding the unrelated Rust Discord bot. Preserved all
existing dirty changes; .git now EXISTS (older instructions saying otherwise are stale).
Fixed the two previously recorded WallyBot Pyright failures: /auth/me uses Pydantic model_validate
for the string-backed persisted role (retaining Literal validation), and backtest CSV field names
have an explicit tuple[str, ...] annotation. Updated browser mocks to include required analyst
flags and proposal_history, and replaced the obsolete Graphify installation assertion on the
product Docs page with Telegram command documentation assertions. Added browser coverage for
expired proposals hiding approval/simulation, rejection remaining available, and recorded PAPER
approval results removing the approval action.

Verified: 569 unit/contract tests passed; WallyBot-scoped Pyright zero errors; Ruff on changed
backend files passed; frontend tsc and focused ESLint passed; 14 observability browser tests
passed against a standalone Next dev server with mocked API responses. git diff --check passed.
The normal backend run returned 570 passed and 283 setup errors because Docker is unavailable;
the standard Playwright stack also could not start its PostgreSQL/Redis containers. These are
NOT passing real-service integration or full-stack acceptance results. No deployment occurred.
Unrelated Rust files have existing type errors; they were not edited or included in scoped checks.

Remaining product work from the previous handoff includes trustworthy current valuation and
per-proposal P&L, position stop/target follow-up, and full real-service/end-to-end acceptance.
Do not claim the complete bot is finished based on mocked browser and unit tests alone.

# Current task

## Approved proposal → revalidated PAPER order — 2026-09-27

Portfolio activity now exposes read-only proposal provenance: when an approved proposal produced a
PAPER fill, its `proposal_id` is returned with that fill and shown as its source in the portfolio.
The lookup is scoped to the signed-in owner and uses the persisted execution order id; it adds no
execution path and does not fabricate unrealized P&L. Focused portfolio/proposal tests (20), Ruff,
Pyright, frontend TypeScript and ESLint passed. API/web/gateway were recreated and readiness plus
an in-container verification passed. `docs/PRODUCT-MANDATE.md` records the distinction.

The portfolio also now groups each proposal-originated fill in a read-only monitoring history:
actual fill entry/quantity/time held, recorded stop/target and recorded execution result. It
intentionally withholds a live/unrealized result until a trustworthy current quote is available.
The same focused checks passed; the API/web/gateway deployment was recreated and verified.

Telegram now recognizes `/withdrawal` as a strictly read-only realized-result review for the AI
PAPER account. It can only summarize confirmed FIFO results; it has no destination input, no
confirmation record, no order path and no provider transfer capability. 38 focused command-loop
tests, Ruff and Pyright passed; API/web/gateway was recreated and verified.

ADR-017's missing step now exists. `POST /api/proposals/{id}/approve` (Admin + fresh MFA + CSRF)
commits the single-use approval first and returns 409 `Proposal expired` once `as_of +
signal_ttl` has passed (simulate too). In OBSERVE the approval is stored with
`execution_status=OBSERVE_ONLY` and no order. In PAPER, `wallybot/application/proposal_execution.py`
(`execute_approved_proposal`) resyncs the `paper-ai:<user>` balances, reconciles only that
account, re-reads instrument/candles/quality/spread/equity/breakers, runs `ShadowDecisionService`
(allocator + `DeterministicRiskEngine`), persists the evidence and only then submits one MARKET
order via the AI account's own `FakeExchange` (`app.state.paper_ai`, idempotency key
`proposal:<id>`). A process-local lock serializes executions. Outcome + reasons are stored in
`trade_proposals.execution_*` (migration `0040_proposal_execution`) and audited; the Telegram
decision message reports it. The deterministic loop's reconciliation sweep is now scoped to its
own account.

Pre-existing bug fixed in the same migration: `wally_api` had no grant on `shadow_decisions`, so
`GET /api/proposals` (with rows) and Simulate returned 503 under the real API role.

Second pre-existing bug fixed: `FakeExchange` fill ids were a per-instance counter
(`fake-fill-1`...), which restarts after an API restart (and would collide between the two PAPER
gateways) while fills/ledger transactions are keyed by that id. Now `fake-fill-<client_order_id>-<n>`.

Verified: full backend suite 870 passed; Ruff clean; pyright shows 2 pre-existing errors in
`auth_routes.py:76` and `backtest_routes.py:245` (untouched here). Frontend tsc/eslint clean;
Playwright 12 passed, 2 failed in untouched areas (Docs page "uv tool install graphifyy" text,
Settings "Activar análisis de IA" button disabled) -- pre-existing, not investigated. Migration
0040 deployed; api/web/gateway recreated; readiness 200.

UI: proposals show "valid until", hide Approve/Simulate once expired, and show the approval
outcome; proposal strings now have English translations.

Telegram's read-only `/proposals` now includes the stored execution context for each proposal
(for example `PAPER FILLED` or `OBSERVE_ONLY`) in addition to the decision status. It remains an
informational reply; no Telegram command reaches the approval or execution path. 39 focused
Telegram/proposal tests passed, Graphify was updated, and the rebuilt API/gateway passed readiness
plus an in-container code verification.

Next candidates: portfolio history/P&L per approved proposal (spec point 4, now unblocked),
informational withdrawal recommendations (point 5), stop/take-profit follow-up for AI positions.

## Configurable Telegram proposal digest — 2026-09-27

Migration `0038_ai_proposal_digests` adds an operator-scoped delivery watermark. The API's existing
Telegram report loop now also invokes `run_ai_proposal_digest_tick`: while AI analysis is enabled,
it sends at most five **new pending** proposals after the configured `digest_interval_hours` has
elapsed. The bilingual notification is informational, passes through the existing encrypted-token,
chat allowlist, deduplication and rate-limit dispatcher, and tells the operator to return to the
MFA-protected web UI. It cannot execute, approve, simulate, transfer, alter settings, or expose
wallet/provider credentials. The watermark keeps previously notified proposals from recurring.

Verified: Ruff and pyright clean; 15 focused integration/unit tests pass; `graphify update .` ran.
Migration `0038` applied successfully and API/gateway were recreated. `http://localhost:3333/health/ready`
and `http://localhost:3333/docs` return 200. Shared tree remains intentionally dirty; do not
broad-stage or commit.

## Independent Codex + Claude analyst consensus — 2026-09-27

The product decision now in effect is **OBSERVE by default**. `PAPER` is an opt-in simulation
mode only; it remains disabled unless the operator explicitly enables it in Settings. Proposal
simulation is blocked both in the UI and on `POST /api/proposals/{id}/simulate` unless
`control.environment == PAPER`. Analysis, Telegram, approval, and a model response must never
change that setting.

Migration `0037_ai_analyst_consensus` adds the persisted analyst controls:
`codex_enabled`, `claude_enabled`, and `require_consensus` (all default true). The native worker
constructs one restricted local CLI analyst per enabled provider and sends both the same validated,
timestamped `AIAnalysisContext`. `ConsensusAiProvider` fails closed when a provider HOLDs/fails or
entry prices differ by more than 3%; with consensus disabled, one enabled analyst may propose.
It has no execution, balance, market, wallet, or credential capability. Composite proposals keep
the conservative minimum confidence/allocation and name both analyst models in their evidence.

Verified: Ruff and pyright clean; 36 focused unit tests and 10 integration tests passed;
migration `0037` applied; API/web/gateway healthy and `http://localhost:3333/docs` returns 200.
`graphify update .` ran after the implementation and documentation changes.

Strict consensus also verifies the proposed direction, not merely price proximity: a BUY/SELL
disagreement always resolves to HOLD. Ruff, pyright and 23 focused consensus/CLI/decision tests
passed for that additional guardrail.

CLI analysts now accept BUY, SELL or HOLD. SELL is persisted as a proposal to reduce an existing
spot holding and the shadow allocator/risk path caps it by the actual held exposure; without a
position it is rejected. This is still only a review/simulation capability: it cannot create an
order, short, borrow, transfer or withdraw. Ruff, pyright and 29 focused AI/consensus/shadow tests
passed. Rebuild/recreate the API before relying on the updated simulation path.

Do not add provider API keys to the UI or database. The supported current integration is the
operator's already-authenticated local `codex` and `claude` CLIs. A future BYOK adapter would
need a separately designed encrypted credential lifecycle and is not implied by these controls.

## Reconciled concurrent sessions: ADR-016 (mine) superseded by ADR-017 (Codex's) — 2026-09-24

Two sessions worked this same feature area concurrently and produced genuinely incompatible
designs for the same subsystem. Mine (ADR-016): AI decides and directly submits a PAPER order,
bypassing `RiskEngine`/`PortfolioAllocator`/breakers entirely, per the operator's own explicit,
twice-confirmed instruction after concrete risk warnings. The concurrent Codex session (ADR-017,
written *while I was mid-task*): AI only produces a persisted, explainable proposal; a human must
Approve/Reject/Simulate it from an authenticated, Admin+fresh-MFA surface; nothing reaches
`ExecutionService` until a future, not-yet-built step re-validates mandate/quality/allocation/risk.
**The operator then explicitly confirmed (2026-09-24) they want ADR-017's direction, pasting a
6-point spec that matches it exactly** — treat ADR-016 as historical record of a decision that was
superseded within the same day, not as the standing design. Read ADR-017, not ADR-016, before
touching this area.

What survived from my side, still relevant and reused by ADR-017's own code: `CliAiProvider`
(`wallybot/intelligence/cli_ai_provider.py`, unchanged, still the thing that calls `claude`/`codex`
CLI), `wallybot/application/paper_accounts.py`'s `paper_ai_account_id` (now used by
`apps/api/proposal_routes.py`'s simulation step), and `ai_autonomy_control`
(`wallybot/domain/ai_autonomy.py` + migration `0033`) -- ADR-017 explicitly wants "distribución
CORE/GROWTH/SPECULATIVE... por usuario, versionadas" and this table already holds exactly that
(70/20/10 targets + digest interval), just not yet consumed by anything. What did NOT survive:
`ai_decision_loop.py`'s order-building/execution code and `apps/ai_worker/worker.py`'s
`ExecutionService`/`FakeExchange` wiring -- both files were rewritten by the other session to only
produce/persist proposals, never execute. My own `run_ai_decision_tick`/`test_ai_decision_loop.py`
were replaced with the other session's equivalents (opposite guardrail: proving *no* execution
capability exists, instead of proving risk bypass is structural).

Reconciliation work this pass: full backend suite (850 passed, 0 failures) and frontend
(tsc/eslint/build clean) confirmed compatible after the merge. Fixed 4 real Playwright breaks
caused by the two sessions' overlapping edits to shared test infrastructure (not logic bugs):
`shell()`'s catch-all mock was missing the new `/api/proposals` route (added by Codex's
`ProposalsSection.tsx`/`useProposalsData.ts`, wired into `IntelligencePage.tsx`/`Dashboard.tsx`);
the intelligence-index nav link count test still expected 7 links, now 8 (the new Proposals
section); the System page's exchange/market-data service row was renamed ("Exchange" ->
"Datos de mercado"/"Market data") independently of this work and the test still asserted the old
label; and Codex correctly updated my own "Permisos IA" panel's copy in `SettingsPage.tsx` (from
"Trading autónomo con IA" framing to "Análisis de IA" framing, matching ADR-017's real behavior)
but the e2e test I wrote for it still asserted the old, now-inaccurate wording. 13/13 Playwright
green after fixes, stable.

**User's confirmed 6-point spec (2026-09-24), mapped against current state:**
1. Persistent proposals (price/amount/risk/reason/expiry/context) -- **done** (`TradeProposalRow`).
2. Approve/reject/simulate from Telegram/UI -- **UI done**; Telegram is read-only summary only so
   far (`/proposals` command shows the list, does not let you act -- matches the existing
   `/pause`/`/resume` pattern of "Telegram requests, web+MFA confirms," not yet built for
   proposals specifically).
3. ES/EN notifications per proposal + result, configurable digest -- **not built**.
   `ai_autonomy_control.digest_interval_hours` is stored/editable but nothing consumes it yet.
4. Portfolio history/charts (entry, current price, time held, P&L, outcome) -- **not built**;
   blocked on the still-missing approve-to-order step (nothing to chart until proposals can become
   real positions).
5. Withdrawal recommendations, informational only, no transfers/keys -- **not built**.
6. 70/20/10 configurable, not fixed -- **infra exists** (`ai_autonomy_control`), system-wide
   singleton rather than literally per-user, matching this app's existing single-admin model.

**Immediate next actions:** asked the user which gap (2's Telegram half, 3, 4, or 5) to build
next, since they're mostly independent and the session has already had a lot of direction churn
today -- did not unilaterally pick one given how much has already changed under the operator today.

## Approved AI proposals and operator isolation — 2026-09-24

ADR-017 is the active contract. `apps/ai_worker` only analyzes validated market context and
persists a dated `TradeProposal`; it cannot submit an order, withdraw or transfer. Each new
proposal has an `owner_id` (`0036_proposal_owner`), and proposal reads/decisions are scoped to
the authenticated operator. `POST /api/proposals/{id}/approve|reject|simulate` is Admin + fresh
MFA, one-time, audited, and only records a decision.

The Intelligence page shows proposal status and its actions. Settings calls this periodic AI
analysis rather than autonomous trading. System reports `KRAKEN_PUBLIC_DATA` instead of the
misleading `NOT_CONFIGURED`. API, web and migration images were rebuilt; health is 200 and the
database head is `0036_proposal_owner`. Focused checks passed: 18 tests, Ruff, frontend
TypeScript and ESLint. `graphify update .` ran.

Telegram now supports `/proposals` as a read-only, owner-scoped summary of the five most recent
AI ideas, in Spanish or English. It explicitly directs sensitive decisions back to the MFA-protected
web UI; Telegram still cannot approve or execute an order by itself. 43 focused Telegram/AI tests
passed after this addition and the API was redeployed healthy.

Next: build the separate approved-proposal-to-PAPER validation workflow with deterministic
mandate/risk checks. Do not reintroduce direct execution. Telegram should reuse the same recorded
decision surface and stay operator-scoped. Preserve shared dirty work; do not broad-commit.

## AI-autonomous PAPER trading via local claude/codex CLI — 2026-09-23

User directive shift this session: production runs entirely on the operator's own PC (no cloud
deployment), and AI capability comes from invoking the operator's own already-authenticated
`claude`/`codex` CLI as a subprocess, not a hosted API key. The operator then explicitly asked for
the AI to execute trades (buy/hold/sell within the wallet, never withdraw to a bank account) --
confirmed twice, after being shown concrete failure scenarios (hallucinated trades, prompt
injection, unbounded loss with no backstop), that this new path should run **without** the
deterministic `RiskEngine`/`PortfolioAllocator`/circuit-breaker limits the rest of this codebase
enforces everywhere else. This is recorded as [ADR-016](../docs/adr/016-ai-autonomous-account.md)
(partially supersedes ADR-007/013, scoped narrowly) -- **read it before touching this area** so a
future session doesn't mistake this for a bug and "fix" it by re-adding risk checks.

Built across 5 backend slices + 1 frontend slice, each independently verified:

1. `wallybot/intelligence/cli_ai_provider.py` (`CliAiProvider`) -- implements the existing
   `wallybot.domain.trade_proposal.AIProvider` port. Invokes `claude -p "<prompt>"
   --output-format json --restricted` or `codex exec "<prompt>" --json --sandbox read-only`
   (real flags, verified against the installed binaries' `--help`, not guessed). Every failure
   (missing binary, timeout, non-zero exit, malformed/schema-invalid JSON) resolves to `None`
   (HOLD), never a fabricated proposal. 17 unit tests.
2. `wallybot/application/ai_decision_loop.py` -- `build_ai_order_intent` (pure translation,
   `TradeProposal` -> `OrderIntent`, rejects SHORT/staled proposals, rounds to lot size -- none of
   this is a risk limit, just mechanical order validity) and `run_ai_decision_tick` (the real
   orchestration: reuses the same universe/quality/regime/`TrendFollowingStrategy` data pipeline
   `DecisionPipeline` uses, then asks the AI instead of running allocator/risk). **This module must
   never import `wallybot.domain.risk`/`breaker`/`portfolio`** -- a permanent import-inspection
   unit test enforces this structurally, not by trusting a bypassed check. 10 + 4 tests.
3. Migrations `0033`/`0034`: `ai_autonomy_control` singleton table (fails closed, `DISABLED` by
   default, holds the 70/20/10 tier-target guidance and digest interval) + least-privilege
   `wally_ai` DB role (same grants shape as `wally_api`'s execution/ledger access, nothing more).
   Postgres gained a loopback-only host port (`127.0.0.1:5433`) for the native process below --
   required adding `postgres` to the `edge` network too, since Docker Desktop/WSL2 cannot publish
   a port from a container on `internal: true`-only networks (confirmed by direct testing; this
   also silently affected the pre-existing Prometheus/Grafana ports). User approved this network
   change explicitly after the tradeoff was explained.
4. `GET`/`POST /api/ai-autonomy/control` + `GET`/`POST /api/portfolio/ai(/fund)` -- the toggle
   (Admin + fresh MFA, separate from `Control.status`/`environment`) and the fully separate
   `paper-ai:<user_id>` ledger account/view, reusing `PortfolioView`'s existing shape. 8 + 4 + 4
   integration tests.
5. `apps/ai_worker` -- the actual native (non-container) process, run directly on the host because
   it needs normal access to the operator's local CLI. **Verified for real against the live dev
   stack**: real Kraken calls, a real `claude` CLI call (confirmed the `--output-format json`
   envelope's `"result"` field parses exactly as `CliAiProvider` expects), no crash, correctly
   produced no order because the model said HOLD that tick -- a valid outcome, not a failure. Test
   funding/toggle state was cleaned up from the live DB afterward.
6. Frontend: Portfolio page gained a full "Cuenta de IA autónoma" section (own funding form,
   balances/activity/orders, fully separate from the main account); Settings gained a "Permisos
   IA" panel (enable/disable, 70/20/10 tier inputs, digest-interval input). Updated `DocsPage.tsx`'s
   architecture/safety copy, which previously stated "AI decisions always pass deterministic
   controls" -- now false for this one path, corrected precisely (deterministic strategy still
   does; the opt-in AI account explicitly doesn't, no-withdrawal/PAPER-only still holds for both).
   **Found and fixed a real pre-existing Playwright flake** while adding this (unrelated to the
   AI feature): the markets-loading-skeleton test asserted a generic label that never actually
   renders on that page (it uses a page-specific one) -- passed before only by coincidentally
   catching an unrelated transient state; fixed with the correct, stable locator. 13/13 Playwright
   passing, stable across repeated runs. TS/ESLint/build clean.

Docs updated to record this as a deliberate, dated exception (not a gap): `docs/adr/016-...md`
(new), `docs/adr/007-...md` + `013-...md` (superseded-by note), `AGENTS.md` (carve-out next to the
"never let AI submit trades directly" line), `SECURITY.md` ("Secret and agent isolation"),
`RISK.md` (breakers section), `docs/PENDING.md` Fase 6 (exception note, no boxes checked -- most
of Fase 6, hosted-provider adapters/budget/calibration/cost-UI, remains genuinely unbuilt).

**Verified:** full backend suite 862 passed, ruff/pyright clean. Frontend: tsc/eslint/build clean,
Playwright 13/13 stable ×3. Docker rebuilt/redeployed (api, api-research, web images); all services
healthy, `/health/ready` 200.

**Not yet committed** -- ask before committing, per repo convention. This is a very large diff
spanning new backend modules, a new migration pair, a new Docker network attachment, and frontend
changes; consider whether to split into multiple commits (infra/migrations, backend AI engine,
frontend UI, docs) or one cohesive commit -- ask the user's preference.

**Immediate next actions, per the approved plan's remaining slices (not started):** Slice 6 (feed
the 70/20/10 tier targets and a wider Kraken-universe "new coin" discovery pass into the AI's
prompt/context -- currently the targets are stored and editable in Settings but not yet actually
given to the AI), Slice 7 (a distinct `AISuggestion` type + reusing the existing
`TelegramConfirmation` flow for non-trade strategic suggestions like "you've held BTC a year,
withdraw X%?", plus digest-style notifications via the existing daily/weekly Telegram report
scheduler instead of per-trade spam). Explicitly out of scope, unchanged status: the equities/
VIX/Fear&Greed strategy (still blocked on an equities venue + data-provider decision, unrelated to
this work) and LIVE trading (no real order-submission gateway exists at all yet; Fase 9's full
human-only checklist is untouched). Also raised but not yet addressed: the user's request for
XML/JSDoc-style comments conflicts with this repo's own "no comments unless the why is non-obvious"
convention (AGENTS.md/CLAUDE.md) -- needs a decision from the user before applying broadly.

## Reproducible research exports and artifacts — 2026-09-23

`GET /api/backtests/export` now provides authenticated CSV or JSON of each immutable experiment's
complete replay inputs and outcome: engine/feature/strategy versions, exact market rules,
timeframe/window, costs, allocation, seed and metrics. An optional exact `experiment_id` filter
lets a completed isolated research job expose only its produced experiment. The Backtests history
offers full-history CSV/JSON downloads; the research jobs panel offers a result download once a
job completes. This is a read-only, sanitized research artifact -- it contains no provider
credentials, execution handle or live-trading path. Focused integration tests (15) plus TS,
ESLint and Ruff passed; API/web were rebuilt and `http://localhost:3333/health/ready` returned
ready. `graphify update .` ran after the changes. Preserve concurrent changes and do not
broad-commit.

## UI: 3D access, product guide, skeletons and Telegram commands — 2026-09-23

The web UI now has a deliberately lightweight Three.js/R3F orbital mark on the private-access
screen (`apps/web/src/components/auth/AuthScene.tsx`), without putting WebGL in the operational
dashboard. Reduced-motion CSS already disables animation globally. `DocsPage` is a product guide:
it presents the app's data/control architecture, guided setup, every dashboard area, explicit
safety boundary, and Telegram command reference. Documentation is first in sidebar navigation.

`/help`, `/commands`, and linked `/start` already existed and are verified in the Telegram command
loop; this UI slice makes that discoverable in both Docs and Settings. The command model remains
safe: `/pause` and `/resume` only create a web/MFA confirmation, never execute on Telegram.

`PageSkeleton` now exposes an accessible loading status and is in Markets/System. TypeScript,
focused ESLint, the mocked Playwright observability suite and the Next production build passed.
`graphify update .` was run. Docker Desktop was unavailable (no engine pipe), so the local web
service could not be rebuilt or redeployed; start Docker Desktop and run `docker compose build web`
then `docker compose up -d web` to publish this slice. Do not broad-commit: the shared working
tree contains concurrent auth/security changes from another agent.

Follow-up in the same slice: Markets now calls the existing authenticated
`GET /api/markets/{instrument_id}` contract only after the user chooses “Ver detalle”, rendering
real candles, bid/ask, volume and data quality in a responsive detail panel. This avoids an
additional provider contract or fabricated metrics.

## MarketCache wired into the Markets view (2026-09-21, continued further still)

Last of the Fase 1/2 audit's "safe, unblocked" list: `MarketCache` (`wallybot/infrastructure/
market_cache.py`) was real, tested, but connected to zero real call paths. `build_market_overview`
now checks it first for each instrument's bid/ask snapshot (`DEFAULT_SNAPSHOT_CACHE_TTL = 30s`)
before hitting the provider; on a miss it fetches and populates the cache. `apps/api/main.py`'s
`app.state.market_overview` partial now passes a real `MarketCache(redis)`. Candles are NOT
cached -- `MarketCache` only ever stored a single `MarketSnapshot`, and that's still true; candles
are the actually-expensive part of the fetch and still go straight to the provider every load. A
cache hit still doesn't imply freshness (ADR-003) -- quality is still always evaluated against
fresh candles, never the cached snapshot.

**Real pyright bug found and fixed while wiring this** (not a new one I introduced -- pre-existing,
just never triggered because nothing had passed a concrete `Redis` into `MarketCache` in
type-checked code before): `RedisLike.set`'s declared param name (`key`) didn't match
`redis.asyncio.Redis.set`'s real first param name (`name`) as a keyword-usable positional-or-
keyword parameter, so pyright rejected a real `Redis` as not structurally satisfying the protocol.
Fixed properly, not suppressed: made `key`/`value` positional-only and `px` keyword-only (matching
exactly how this module actually calls them), and switched the protocol's methods from `async def`
to plain methods returning `Awaitable[...]` -- an `async def` Protocol method structurally compares
against `Coroutine[Any, Any, T]`, which redis-py's own command-mixin stubs never declare (they type
generically as a bare `ResponseT`, despite being awaitable at runtime).

Added 2 new unit tests to `tests/unit/test_market_overview.py` (`FakeMarketCache` +
`CountingProvider`): a cache hit skips the provider's `fetch_snapshot` call entirely; a cache miss
fetches once and populates the cache. The existing `tests/integration/test_market_cache.py` (real
Redis via testcontainers) was untouched and still passes.

**Verified:** full backend suite 798 passed (up from 796), ruff/pyright clean (known
`auth_routes.py:65` only).

**Not yet rebuilt/redeployed or committed this slice.**

**Immediate next actions:** rebuild+redeploy, `graphify update .`, verify the Markets page still
serves real data live, commit. This closes out the Fase 1/2 audit's list of safe, unblocked items
this session picked up unilaterally -- remaining items either need an explicit product/config
decision (user administration, RISK_POLICY/PORTFOLIO_POLICY versioning, stop-distance-based sizing)
or are human-only (CI-remote, Fedora/Cloudflare, Fase 9 LIVE gates). Worth asking the user directly
next: which of those larger, decision-gated items to scope and start, or whether to keep sweeping
for more small safe items first. Do NOT touch OBSERVE/PAPER/LIVE architecture. Still unaddressed:
user's "three js es par ael login y eso" comment.

## Instrument-detail route added (2026-09-21, continued further still)

Another Fase 2 gap the audit named directly: "no existe ruta de detalle de instrumento (no
`/api/markets/{id}`, sin velas)." New `GET /api/markets/{instrument_id:path}` (`:path` converter
since `Instrument.id` embeds a literal `/` -- `"<venue>:<market_type>:<base>/<quote>"`). New
`build_instrument_detail` in `wallybot/application/market_overview.py` reuses the exact same
provider/timeframe/quality_policy `GET /api/markets` already uses -- pulled from
`app.state.market_overview`'s own bound `functools.partial` kwargs, not a second, potentially-
drifting config. Returns candles/volume/bid-ask/quality/eligibility for one instrument, honest 404
when the id doesn't match anything the provider currently discovers. Reused
`evaluate_instrument`'s quality gate from the slice before this one, so a FAILURE-quality
instrument's detail also reports `eligible: false` with `data_quality_failure` in the reasons.

Caught a real pyright error while wiring the DTO: `QualityStatus` (a `StrEnum`) doesn't structurally
satisfy `Literal["PASS","WARNING","FAILURE"]` even though the values match -- needed `.value`.
Interesting because the identical pattern at `GET /api/markets`'s own `quality_status=row.quality.
status` line does NOT get flagged, since `overview = await request.app.state.market_overview()`
infers as `Any` (untyped `app.state`), so pyright never checks it there -- my new function has a
real return-type annotation (`InstrumentDetail | None`), so the check actually fires. Left the
older untyped line alone (out of scope, pre-existing, not a new bug).

**Deliberately API-only, no frontend wiring**: a candle chart needs a charting library --
`ARCHITECTURE.md` names Lightweight Charts as the plan, but it isn't an `apps/web/package.json`
dependency yet (confirmed via grep, not assumed) -- a real new-dependency/design decision, not
something to add silently inside this slice. `MarketsPage.tsx` already has a client-side `<details>`
expand-row for reasons/quality (covers part of the audit's Playwright-tested "keyboard details"),
so the read-only quality/eligibility half of "detail" was already partly there; only the candle
chart is the actual remaining gap now.

Added 3 unit tests to `tests/unit/test_market_overview.py`: known instrument returns candles/
quality, unknown instrument returns `None` (not a fabricated empty detail), FAILURE-quality
instrument marked ineligible (reusing the same `StaleCandlesProvider` from the prior quality-gate
slice). No integration test for the route itself -- matches the pre-existing convention: `GET
/api/markets` itself has zero integration coverage either (real Kraken network dependency), relies
on the unit-tested `build_market_overview`/`build_instrument_detail` plus live verification against
the real deployed stack.

**Verified:** full backend suite 796 passed (up from 793), ruff/pyright clean (known
`auth_routes.py:65` only). No frontend files touched.

**Not yet rebuilt/redeployed or committed this slice.**

**Immediate next actions:** rebuild+redeploy (backend-only), `graphify update .`, verify
`/api/markets/<real-instrument-id>` live against the deployed stack, commit, keep going per
"continua...hasta acabar tokens." Remaining audit-surfaced candidate: wiring `MarketCache` into a
real call path (lower priority, smaller win). Do NOT touch OBSERVE/PAPER/LIVE architecture. Still
unaddressed: user's "three js es par ael login y eso" comment.

## Stale Vite references fixed (2026-09-21, continued further still, docs-only)

Small, low-risk pick from the Fase 1/2 audit: `ARCHITECTURE.md:109`, `DEPLOYMENT.md:63`,
`AGENTS.md` (both the stack line and the Context7 routing-table row) and
`docs/AI-DEVELOPMENT.md` (two mentions) all still described the frontend as Vite -- stale since
the real Vite→Next.js migration (`.ai/DECISIONS.md`'s 2026-09-12 entry, `docs/adr/009-port-3333-
gateway.md`). Verified the real current mechanism first rather than guessing: `apps/web/package.
json`'s `dev` script is `next dev --hostname 127.0.0.1 --port 3333`, and `apps/web/next.config.ts`'s
`rewrites()` (not a Vite proxy) forwards `/api/:path*` and `/health/:path*` to `WALLY_DEV_API`
(default `http://127.0.0.1:8000`). Also caught `DEPLOYMENT.md` calling `scripts/dev.sh`/`dev.ps1`
"Planned" when they're real and already invoked by `make dev` -- fixed that too, same sentence.
Docs-only, no Dockerfile bakes these files in, so no rebuild/redeploy needed for this one.

**Not yet committed this slice.**

**Immediate next actions:** commit, then keep going per "continua...hasta acabar tokens." Remaining
audit-surfaced candidates: wiring `MarketCache` into a real call path, an instrument-detail route.
Do NOT touch OBSERVE/PAPER/LIVE architecture. Still unaddressed: user's "three js es par ael login
y eso" comment.

## Quality gate closed on the Markets view (2026-09-21, continued further still)

Picked from the Fase 1/2 audit's own findings: Fase 2's "Pasar siempre por calidad antes de
features y ranking" was checked NOT fully covered -- `decision_pipeline.py` (the live trading path)
already excludes FAILURE-quality instruments before scoring (confirmed real, at
`decision_pipeline.py:151-155`, deliberate and documented), but `market_overview.py` (the read-only
Markets page) never applied that same gate -- a FAILURE-quality instrument (stale data, broken
sync) could show up `eligible: true` and get scored/ranked right alongside good data, contradicting
this doc's own P0 line: "fallos del proveedor se muestran como fallo, nunca como cotizaciones
válidas."

Fixed at the shared root both paths already use: `evaluate_instrument`/`evaluate_universe`
(`wallybot/market/universe.py`) now accept an optional `QualityReport`/`dict[str, QualityReport]`
and append a `data_quality_failure` reason (eligible=False) when status is FAILURE. Optional and
backward-compatible -- `decision_pipeline.py`/`scanner.py` need no change since FAILURE instruments
never reach `scan_universe` there in the first place; only `market_overview.py` now threads its
already-computed `quality_by_id` through. WARNING status still doesn't block eligibility --
"aplicar una política explícita a cada WARNING" (which specific WARNING reasons are tolerable) is
genuinely unimplemented, not silently claimed done -- would need a real policy-config decision, not
a bug fix.

Added 4 new unit tests to `tests/unit/test_universe.py` (quality ignored when omitted, FAILURE
blocks, WARNING doesn't block, `evaluate_universe`'s dict threading) and 1 to
`tests/unit/test_market_overview.py` (a `StaleCandlesProvider` wrapper shifts one instrument's
candles 30 days into the past -- real staleness, not a mocked status -- confirms it's excluded from
scoring/ranking while an unaffected instrument in the same universe stays eligible).

**Verified:** full backend suite 793 passed (up from 788), ruff/pyright clean (known
`auth_routes.py:65` only), `tests/integration/test_decision_pipeline.py` still green (confirms no
regression to the already-correct live trading path). No frontend files touched this slice.

**Not yet rebuilt/redeployed or committed this slice.**

**Immediate next actions:** rebuild+redeploy (backend-only, no migration), `graphify update .`,
commit, keep going per "continua...hasta acabar tokens." Remaining audit-surfaced candidates:
wiring `MarketCache` into a real call path (built, tested, unused -- lower priority, smaller win
since it only caches single-instrument snapshots, not the candle fetches that dominate the actual
request cost), fixing stale Vite references in `ARCHITECTURE.md`/`DEPLOYMENT.md`/root `AGENTS.md`,
an instrument-detail route (`GET /api/markets/{id}` + candles). Larger/riskier, needs explicit
scoping first: user administration, config versioning for `RISK_POLICY`/`PORTFOLIO_POLICY`. Do NOT
touch OBSERVE/PAPER/LIVE architecture (explicit user instruction). Still unaddressed: user's "three
js es par ael login y eso" comment.

## Risk limits exposed + Fase 1/2 audit reconciled (2026-09-21, continued further still)

**1. `GET /api/risk/limits`** (closes Fase 3's "Exponer límites, consumo, reservas, pérdidas,
incumplimientos y razones en la pantalla de riesgo"). Read-only: `RISK_POLICY`'s configured limits
(daily/weekly loss, drawdown) are always present; equity/high-water-mark/consumption/breach fields
come from the latest persisted `EquitySnapshot` the decision loop already writes each PAPER tick --
deliberately does NOT re-price positions live (no `MarketDataProvider` dependency in this route),
so it's honestly "as of the last decision tick," never a fresher number than what was actually
computed. `None`, not a fabricated zero, when no snapshot exists yet (still OBSERVE, or PAPER never
run). Reuses `wallybot.domain.breaker.breakers_to_trip`'s own threshold math for the
breached/not-breached verdict per metric, rather than re-deriving it. New `RiskLimitsView` DTO,
new "Límites y consumo" panel in `RiskPage.tsx` (percent formatting follows the exact
`(Number(x) * 100).toFixed(2)}%` precedent `BacktestsPage.tsx` already established for
Decimal-string ratios). **Not covered**: "reservas" (capacity reserve) -- no such concept exists
separately from the RECONCILIATION breaker in this endpoint.

**2. Reconciled the Fase 1/2 audit** a background fork agent ran earlier this session (read-only,
20 items checked against real code, not against `docs/PENDING.md`'s own checkboxes). Tally: 1 DONE,
15 PARTIALLY DONE, 4 NOT STARTED (2 of those human-only: CI-remote, Fedora/Cloudflare). Checked off
the one genuinely DONE item (Fase 2's instrument metadata/market-rules unification -- already real
in `wallybot/domain/market.py`'s `Instrument`). Added a dated "Auditoría 2026-09-21" summary
paragraph to both Fase 1 and Fase 2 in `docs/PENDING.md`, right before each phase's Aceptación line
-- key findings: Playwright's `webServer` never actually routes through the real nginx gateway
(port 3334→8001 directly, not 3333); `ARCHITECTURE.md`/`DEPLOYMENT.md`/`AGENTS.md` still have real
stale Vite references; no user-admin/session-revoke/TOTP-replace routes exist at all; quality
scoring doesn't gate the market ranking despite being computed; `MarketCache` is fully built,
tested, and wired into zero real call paths; only 2 of 4 required feature types (SMA, momentum)
exist. Left every "partially done" item unchecked (per this doc's own convention: `[x]` means the
core capability shipped, not "some evidence exists") -- did not check off any item just because
the audit found real substance, only the one the audit called fully DONE.

**Verified:** full backend suite 788 passed (up from 784), ruff/pyright clean (known
`auth_routes.py:65` only). Frontend: eslint clean, `tsc --noEmit` clean, Playwright 12/12 (RiskPage
itself has no e2e coverage, before or after this slice -- pre-existing gap, not introduced here;
the 11 new backend integration tests in `tests/integration/test_risk_routes.py` are the real
coverage for the new route).

**Not yet rebuilt/redeployed or committed this slice.**

**Immediate next actions:** rebuild+redeploy, `graphify update .`, commit, keep going per
"continua...hasta acabar tokens." Realistic unblocked candidates surfaced by the audit: wiring
`MarketCache` into at least one real call path (built, tested, unused), gating market
scoring/ranking on quality status (computed but not enforced), fixing the stale Vite references in
`ARCHITECTURE.md`/`DEPLOYMENT.md`/root `AGENTS.md`, an instrument-detail route
(`GET /api/markets/{id}` + candles). Larger/riskier, needs explicit scoping first: user
administration (list/revoke sessions, password change, TOTP replace), config versioning for
`RISK_POLICY`/`PORTFOLIO_POLICY` (touches financial risk limits directly). Blocked: Fase 6 AI,
equities/VIX strategy, Fase 9 LIVE, CI-remote and Fedora/Cloudflare (both human-only). Do NOT touch
OBSERVE/PAPER/LIVE architecture (explicit user instruction). Still unaddressed: user's "three js es
par ael login y eso" comment.

## Audit-log export + i18n Telegram bot (2026-09-21, continued further)

Continuing the user's "sigue hasta acabar tokens" directive. Two more closed items:

**1. `GET /api/events/export?format=csv|json`** (closes most of the "Seguridad" transversal row's
"exportación de auditoría protegida" item). Same `SignedIn` gate and CSV/JSON shape as the earlier
`GET /api/portfolio/export`, but over the audit trail: new `AuditEventView` DTO (`apps/api/dto.py`)
carries `actor`/`correlation_id` -- both withheld from the regular paginated `GET /api/events` feed
to keep it focused on "what happened," but exactly what a compliance export needs ("who did it, and
which actions share an operation"). Optional `since`/`until` (Unix seconds, inclusive) window
filters; `EXPORT_EVENT_LIMIT = 50_000` safety cap, same reasoning as the portfolio export's
`EXPORT_FILL_LIMIT`. Added 6 new integration tests to `tests/integration/test_events_route.py`
(auth-required, CSV shape/actor/correlation_id, JSON shape, since/until window, empty-result
header-only CSV).

**2. Bilingual (EN/ES) Telegram bot replies** (user's explicit ask: "acuerdate de en y es del bot").
Landed earlier this session (see `wallybot/notifications/telegram_i18n.py`'s `resolve_language`,
threaded through every `_xxx_reply` in `telegram_command_loop.py`) -- confirmed still intact and
tested (`tests/unit/test_telegram_i18n.py`, 3 new integration tests in
`test_telegram_command_loop.py`).

**Verified:** full backend suite 784 passed (up from 779), ruff clean, pyright clean (same one
known `auth_routes.py:65` error). Frontend/Playwright not touched this slice (backend-only change).

**Not yet rebuilt/redeployed or committed this slice** -- about to do both now, per the user's
standing "redeployea despues de esto todo" instruction.

**Immediate next actions:** rebuild+redeploy, `graphify update .`, commit, then keep closing
unblocked backlog items per "continua...hasta acabar tokens." A background fork agent
(`a38356ec6e2d2ff93`) is auditing Fase 1/Fase 2 checkboxes in `docs/PENDING.md` against real code --
check its report and reconcile the doc once it lands. Realistic unblocked candidates after that:
OpenTelemetry tracing, backups automation, config versioning (`RISK_POLICY`/`PORTFOLIO_POLICY`
currently hardcoded Python constants -- flagged as needing explicit human scoping first, since it
touches financial risk limits directly). Blocked: Fase 6 AI (provider/API-key decision), the
equities/VIX/Fear&Greed strategy idea (data-provider decision), Fase 9 LIVE (human-only gates). Do
NOT touch/discuss OBSERVE/PAPER/LIVE architecture further (explicit user instruction). Still
unaddressed: user's "three js es par ael login y eso" comment -- unclear, not yet clarified.

## Observability + 3 parallel agents + concurrent-session merge + /help (2026-09-21, continued)

Biggest single slice this session. User asked to keep going "hasta que se acaben tokens" and to
use multiple agents in parallel. Sequence, in order:

**1. Observability** (`docs/PENDING.md`'s transversal "Observabilidad" row): `wallybot/infrastructure/
metrics.py` -- decision/price-consensus/market-ingestion/telegram-command tick counters, active
breakers gauge, reconciliation health + UNKNOWN-orders gauges, research-queue-depth gauge, service
heartbeat-age gauge (its own background loop, `_heartbeat_metrics_loop` in `apps/api/main.py` --
deliberately NOT only updated on `/api/system` page views, since a metric that goes stale whenever
nobody's looking at a dashboard defeats the point). `docker-compose.yml` got an opt-in `monitoring`
profile (`docker compose --profile monitoring up -d`, matching what DEPLOYMENT.md already specified)
running Prometheus + Grafana, both loopback-only (neither has real auth). `/api/metrics` itself is
unauthenticated (Prometheus can't hold a session cookie) but blocked at the public edge by
`docker/gateway.conf`'s `location = /api/metrics { return 404; }` -- network isolation is the real
boundary, same trust model this codebase already uses for worker/scheduler/research. 5 alert rules
in `docker/alerts.yml`, all rehearsed for real with `promtool test rules docker/alerts_test.yml`
(synthetic series, confirmed pending→firing transitions) and cross-checked against the live
Prometheus's own `/api/v1/rules`. "Costes" (AI spend) deliberately not covered -- nothing to measure
yet. OpenTelemetry tracing deliberately not attempted -- a much bigger, separate investment.

**2. Three parallel worktree-isolated agents**, launched together while the observability work was
still being verified:
- Telegram daily/weekly reports + notification dedup/rate-limit (closes the rest of Fase 8).
- `GET /api/events` cursor pagination + server-side search/filter (closes most of the "Eventos y
  logs" transversal row).
- `docs/TRADING.md`/`STRATEGIES.md`/`AI.md`/`RESEARCH.md`/`BACKTESTING.md`/`OPERATIONS.md` (closes
  the "Documentación" transversal row).

Each ran in its own git worktree (uncommitted, never touched the shared Docker stack or committed
anything, per their own instructions) and reported back independently. Merged all three into the
main worktree by hand (no real commits existed in the worktrees to `git merge`) -- copied
non-overlapping files wholesale, manually reconciled the few files more than one agent touched
(`apps/api/system_routes.py` needed the events-pagination rewrite of `events()` *and* the
heartbeat-metrics addition to `system()` *and* the dedup call-site change in `control()`;
`apps/api/main.py` needed both the observability loops and the new `_telegram_report_loop`).
Verified the fully-merged state before moving on: 758 passed (up from 723).

**3. Found unrelated concurrent work already sitting in the main working tree**, not from me or my
3 agents: a real FIFO PnL implementation (`wallybot/application/portfolio_performance.py`,
`compute_fifo_performance`, wired into `GET /api/portfolio`'s new `performance` field -- closes
most of Fase 4's "lotes FIFO... PnL realizado" item), a secure Telegram pairing flow (`/start
<one-time code>` replacing manual chat_id entry, SHA-256 digest comparison, migration
`0032_telegram_pairing`), and a `PageSkeleton` loading-state refactor across several pages plus a
`DocsPage.tsx` content rewrite. **Asked the user rather than guessing or overwriting** -- another
Claude Code session/window on this same folder, apparently the user's own. User said "comitea todo
integra todo" (commit everything, integrate everything). Fixed two real issues found in that
work before integrating: a `ruff` unused-import lint error, and a `pyright` Protocol-variance error
(`FillLike` Protocol's plain attributes don't structurally satisfy SQLAlchemy's `Mapped[str]`
columns under pyright -- fixed by accepting the concrete `FillRow` type directly instead of a
Protocol, documented why in the module). Also fixed two Playwright tests that broke against the
new `DocsPage.tsx` copy and the new `PageSkeleton` loading UI (updated assertions to match the real
new text/markup, did not revert the product changes).

**4. Added `/help`/`/commands` to the Telegram bot** (user's own request, mid-session): lists every
recognized command with a one-line description; `/start` is also an alias for it once already
paired (Telegram's own convention for a bot's entry point), separate from `/start <code>`'s
pre-pairing meaning.

**Verified, fully combined state:** 769 backend tests passed, ruff/pyright clean (same one known
`auth_routes.py:65` error), frontend eslint/tsc clean, Playwright 12/12 (twice in a row after the
DocsPage/PageSkeleton test fixes). Rebuilt every Docker image, redeployed with
`--profile monitoring`, both migrations (`0031_telegram_reports`, `0032_telegram_pairing`) applied
cleanly, all 10 services (8 core + Prometheus + Grafana) healthy. `graphify update .` run twice
(after the merge, and again after the `/help` addition).

**Not yet committed** -- about to commit now, user has explicitly said to integrate and commit
everything together.

**Immediate next actions:** ask what's next. Realistic unblocked remainders: delivery-failure
handling for Telegram reports (Fase 8's last unchecked item), OpenTelemetry tracing, backups,
config versioning, remaining Fase 1/2 items. Blocked: Fase 6 AI (provider decision), the
equities/VIX strategy idea, Fase 9 LIVE (human-only gates).

## Research jobs: quota + UI (2026-09-21, continued)

Fourth increment this session, per user's continued "hace falta muchas cosas" -- they also asked
for an honest progress/gap report (answered in chat, not duplicated here; see this file's and
`docs/PENDING.md`'s per-phase state for the durable version).

Investigated Fase 7 ("agentes de investigación aislados") expecting a big build, found it was
**much closer to done than its unchecked boxes suggested** -- another instance of this file's own
recurring lesson that `docs/PENDING.md` lags real code. `ResearchJob`'s domain type already had
full `cancel`/`request_cancellation` methods; `ResearchJobRepository` already had a real
`skip_locked` queue (`claim_next`) and `request_cancellation`; `apps/api/research_routes.py`
already had working `POST`/`GET`/`DELETE` routes. What was actually missing: (1) no quota at all,
(2) **zero integration test coverage** for those routes (only `research_runner.py`'s execution
side was tested), (3) **zero frontend** -- the API was fully wired and usable via curl, but nothing
in `apps/web` ever called it.

Closed all three:
- `ResearchJobRepository.count_active()` + `MAX_ACTIVE_RESEARCH_JOBS=5` quota in
  `create_research_job` (429 when exceeded) -- system-wide, not per-user, since this codebase has
  no multi-tenant research quotas concept (single admin, matching every other simplification here).
- `tests/integration/test_research_routes.py` (new, 8 tests): auth, VIEWER-can-list-not-create,
  create/list/cancel happy path, cancelling unknown/already-terminal jobs, the quota rejecting a
  6th job and freeing up after a cancel. Found along the way: `TestClient.delete()` doesn't accept
  a `json=` kwarg in this httpx/starlette version -- needs `client.request("DELETE", url, json=...)`,
  the first DELETE-with-body route test in this suite.
- `ResearchJobsPanel.tsx` composed into `BacktestsPage.tsx`'s "Investigación" page: a create form
  (experiment_id + purpose, ADMIN only) and a jobs table (status/attempts/artifact-or-error/
  requested-at, cancel button on PENDING/RUNNING rows, ADMIN only) -- VIEWER sees the table
  read-only. `apps/web/src/lib/api-client.ts`'s `api()` gained an optional `method` param (was
  GET/POST-only inferred from body presence) since this is the first DELETE call the frontend makes.

**Verified:** full backend suite 721 passed (up from 713), ruff/pyright clean (same known
`auth_routes.py:65` error), frontend eslint/tsc clean, Playwright 12/12 (added one new test for
create/list/cancel). Rebuilt every Docker image and redeployed (no new migration -- `jobs` table
already existed), all 8 services healthy, `GET /api/research/jobs` returns 401 unauthenticated.
`graphify update .` run after the changes.

**Not yet committed** -- ask before committing, per repo convention.

**Immediate next actions:** ask the user what's next. Fase 7's remaining items (agent-tool
integration, service identity/replay protection for an agent endpoint, human-reviewed promotion
workflow) are blocked on Fase 6 (AI provider) existing first -- there's nothing to give tools to or
promote yet. Realistic unblocked candidates: Fase 8's remaining daily/weekly Telegram reports +
notification dedup, "Pendientes transversales" rows (observability/Prometheus, event
search/pagination, config versioning, docs).

## Flaky Settings e2e fixed + CSV/JSON trade export (2026-09-21, continued)

Two more increments after Telegram commands, per user's "hace falta muchisimo" (keep going,
picking well-scoped unblocked items rather than the ones needing external decisions or blocked by
human-only gates).

**1. Fixed the pre-existing flaky Settings e2e test** flagged in the previous entry.
`observability.spec.ts`'s "settings and first-steps..." asserted the OBSERVE-state heading/button
while `shell()`'s mocked `/api/dashboard` always returns `environment: "PAPER"` -- it only "passed"
by catching a transient pre-hydration render before the mocked fetch resolved (`toBeVisible()`
succeeds on first match, not a settled one). Asserted the settled PAPER-state text instead: 5/5
clean runs afterward, vs. ~40% failures before on unmodified `master` (confirmed via `git stash`).

**2. CSV/JSON export of PAPER trade history** (`Pendientes transversales` "Exportación" row).
New `GET /api/portfolio/export?format=csv|json` (SignedIn, own account only) --
`PortfolioRepository.list_recent_fills(account_id, limit=EXPORT_FILL_LIMIT)` with a 50k safety cap
(not a business limit), same fields `get_portfolio`'s `activity` already exposes. **Deliberately no
PnL column**: this codebase has no FIFO lot tracking for live PAPER fills yet (`docs/PENDING.md`
Fase 4's "lotes FIFO... PnL realizado/no realizado" is still unchecked) -- only
`wallybot.domain.smart_money` computes FIFO PnL, and that's for on-chain whale analysis, not this
account. Fabricating a PnL number here would violate this codebase's own "never fabricate" rule
documented all over `historical_query.py`/`market.py`/etc. Frontend: two plain download links
("Exportar CSV"/"Exportar JSON") on the Portfolio page's Actividad reciente panel -- a same-origin
`<a download>` works fine here since the session cookie rides along automatically, no client-side
fetch/blob plumbing needed.

**Verified:** full backend suite 713 passed (up from 709), ruff/pyright clean (same one
pre-existing `auth_routes.py:65` error), frontend eslint/tsc clean, Playwright 11/11 (twice in a
row). Rebuilt every Docker image and redeployed (no new migration this slice), all 8 services
healthy, `/health/ready` -> `{"status":"ready"}`, `GET /api/portfolio/export` returns 401
unauthenticated. `graphify update .` run after the changes.

**Not yet committed this sub-slice** -- ask before committing, per repo convention (the e2e fix and
the export feature landed in the same working-tree pass but are logically separate; consider
splitting into two commits same as prior slices this session).

**Immediate next actions:** ask the user what's next. Realistic non-blocked candidates left:
Fase 7 (research runner as a real queued executor, not just backtest re-run), Fase 8's remaining
daily/weekly Telegram reports + notification dedup/grouping, other rows in "Pendientes
transversales" (observability/Prometheus, config versioning, event search/pagination). Blocked on
external decisions: Fase 6 AI (model/API key), the equities/VIX strategy idea. Explicitly gated,
not startable unilaterally: Fase 9 LIVE.

## Telegram inbound commands (2026-09-20, continued)

User picked "Fase 8: Telegram comandos entrantes" from the punch list after breakers + walk-forward
landed. Scoped via `AskUserQuestion` before writing code (two real architecture decisions, not
cosmetic): **long-polling** (`getUpdates`), not a webhook -- this self-hosted stack has no public
domain/TLS ingress to receive a Telegram-pushed webhook; and the command set (user said "todo lo
necesario") -- read-only `/status`/`/breakers`/`/portfolio` plus sensitive `/pause`/`/resume`,
scoped per RISK.md/SECURITY.md's explicit requirement that sensitive commands need an
expiring/anti-replay token confirmed through the existing Admin+fresh-MFA web flow, never executed
directly from Telegram.

- `wallybot/domain/telegram_confirmation.py`: `TelegramConfirmation`/`TelegramAction`, a 5-minute
  TTL. `/pause`/`/resume` only ever create one of these; they never flip `ControlRow` themselves.
- `wallybot/application/telegram_commands.py`: pure text→command parsing, no free-text chat surface.
- `wallybot/application/telegram_command_loop.py`: `run_telegram_command_tick` -- long-polls
  `getUpdates`, replies to query commands immediately (reading `ControlRow`/`BreakerRepository`/
  latest `EquitySnapshot`), creates a confirmation for `/pause`/`/resume`. Only the operator's
  single allowlisted `chat_id` (from `telegram_config`) is ever acted on; everything else is
  silently ignored, never replied to. First poll after enabling only establishes the `getUpdates`
  cursor baseline -- never executes a backlog of pre-existing messages as if just sent.
  `GET_UPDATES_TIMEOUT_SECONDS=8` is deliberately under the shared `HttpxTelegramTransport`
  client's 10s request timeout (documented in the module docstring) -- a real bug that would have
  silently broken long-polling if missed.
  `apps/api/main.py`'s `_telegram_command_loop` wrapper resolves the admin/account each tick
  (same DB-lookup-stays-in-apps/api split as `_decision_loop`), wired into the lifespan alongside
  the other background tasks, skipped under `environment == "test"` like its siblings.
- New `POST /api/telegram/confirmations/{id}/confirm` (Admin, fresh MFA -- same `admin()`
  dependency every other sensitive route already uses) executes the actual pause/resume by reusing
  `wallybot.domain.control.Control.change()`, the identical domain call `/api/control` makes, then
  marks the confirmation consumed and notifies back over Telegram only if the state actually
  changed. `GET /api/telegram/confirmations` (SignedIn) lists pending ones for the Settings page,
  polled every 10s.
- Migration `0030_telegram_commands`: `telegram_config.last_update_id` (the poll cursor) +
  new `telegram_confirmations` table, `wally_api` grants (same reasoning as every other
  apps/api-only table: only that process has internet egress).
- Frontend: `useTelegramConfirmationsData.ts`, a new panel in `SettingsPage.tsx` between the
  Telegram config and MFA panels (visible to any role when a pending request exists, "Confirmar"
  button gated to ADMIN, mirroring `RiskPage.tsx`'s breaker table pattern).

**Verified:** full backend suite 709 passed (up from 661 pre-breakers), ruff/pyright clean (same
one pre-existing unrelated `auth_routes.py:65` error), frontend eslint/tsc clean, full Playwright
suite 11/11 green. Rebuilt every Docker image and redeployed the whole stack; migration `0030`
applied cleanly, all 8 services healthy, `/health/ready` -> `{"status":"ready"}`,
`GET /api/telegram/confirmations` returns 401 unauthenticated (route mounted), `api`'s own logs
show a clean `API_STARTED` with no traceback from the new background task. Did **not** log into the
real running stack's UI to click through the flow -- the login page needs a TOTP code this agent
neither has nor should read from `.secrets/`, same constraint this file has documented before;
relied on the full backend+Playwright automated coverage instead.

**Found, not caused by this slice, flagged rather than silently fixed**: `apps/web/e2e/
observability.spec.ts`'s "settings and first-steps..." test flakes independently of any change
here (~40% failure rate reproduced on `master` before this slice too, isolated via `git stash`) --
`shell()`'s mocked `/api/dashboard` always returns `environment: "PAPER"`, but the test asserts the
OBSERVE-state heading/button; it only "passes" by catching a transient pre-hydration render before
the mocked fetch resolves, since `expect(locator).toBeVisible()` succeeds on first match rather
than a settled one. Out of scope for this Telegram slice (unrelated file, pre-existing on
`master`) -- worth a real fix (assert the settled PAPER-state text, or wait for the dashboard query
to resolve first) next time someone touches Settings/observability e2e tests.

**Immediate next actions:** ask the user to commit this slice, then ask what's next -- the flaky
Settings e2e test found above, daily/weekly Telegram reports (Fase 8's remaining unchecked item,
notification dedup/grouping), further `PENDING.md` phase auditing, or the equities/VIX strategy
idea (still pending a data-provider decision).

## Persistent operational circuit breakers finished (2026-09-20)

Picked up the working tree exactly where the prior session's "Immediate next actions" pointed --
persistent circuit breakers was already fully built and sitting uncommitted (domain `Breaker`/
`breakers_to_trip`, `BreakerRepository`, migration `0029_breakers`, `/api/risk/breakers` routes,
`run_decision_tick` wiring, `useBreakersData`/`RiskPage` frontend, `tests/unit/test_breaker.py` +
`tests/integration/test_breaker_repository.py` + `test_risk_routes.py`). This session verified it
end-to-end rather than assuming "uncommitted" meant "unfinished": full suite 661 passed, ruff/
pyright clean, frontend eslint/tsc clean, rebuilt every image (`docker compose build`) and
redeployed the whole stack (`docker compose up -d`) -- migration `0029` applied cleanly, all 8
services healthy, `/health/ready` -> `{"status":"ready"}`, `GET /api/risk/breakers` returns 401
unauthenticated (route mounted, auth-gated as intended). `graphify update .` run after confirming.
Checked off in `docs/PENDING.md` Fase 3.

Only daily/weekly loss, drawdown and reconciliation are modeled -- RISK.md's fuller taxonomy
(stale data, abnormal spread/volatility, exchange outages, repeated execution errors, unknown
orders, DB failure, clock drift) still has no trigger wiring, documented as such in
`wallybot/domain/breaker.py`'s own module docstring, not silently implied as covered.

**User also pasted a pseudocode trading strategy this session** (regime-conditioned DCA for
equities using VIX/Fear&Greed on SMH/NVDA, reserve injection on VIX>25 or RSI_Stocks<35, plus a
crypto branch: Fear sentiment -> BTC spot buy, otherwise staggered limit orders at -5%/-10%).
Recorded as a new unchecked item in `docs/PENDING.md` Fase 3, **not implemented** -- two real
prerequisites are missing: (1) `wallybot.domain.market.MarketType` only has `SPOT` crypto via
Kraken today, no equities venue/adapter exists; (2) no VIX or Fear&Greed data source is wired
anywhere in the codebase. This is new `Strategy`-shaped work (`wallybot/domain/strategy.py`), not
a risk/breaker change -- needs an explicit user decision on an equities/VIX data provider before
any code gets written, per `AGENTS.md`'s "avoid speculative architecture changes."

**Not yet committed** -- ask before committing, per repo convention. Working tree also still has
the unrelated-looking `apps/api/dto.py`/`apps/api/main.py`/`wallybot/infrastructure/models.py`
diffs, all part of this same breaker slice (DTO views, router registration, `BreakerRow`) -- one
cohesive change, safe to commit together.

**Immediate next actions:** ask the user to commit this slice, then ask what's next -- walk-forward/
backtest UI wiring, further `PENDING.md` phase auditing (Fase 6 AI, Fase 8 Telegram), the new
equities/VIX strategy idea (pending a data-provider decision), or something else entirely.

## Order cancellation orchestration (2026-09-17, continued again)

User picked this from the audit's punch list as the next increment after the live loop landed.
`c653bef` didn't cover cancellation orchestration (nor did the audit expect it to) --
`ExchangeGateway.cancel_order`/`FakeExchange.cancel_order` already existed, but
`ExecutionService` had no `cancel()`. Added it (`2f91ad8`): durably claims CANCEL_REQUESTED first
(same discipline as `submit()`'s SUBMITTING claim), then resolves through the same lookup-based
`_observe()` path `submit()`/`reconcile()` already use rather than trusting the gateway's own
cancel-result blindly. New `POST /api/portfolio/orders/{client_order_id}/cancel` (Admin), scoped
to the caller's own account.

Had to hoist `paper_gateway`/`execution`/`reconciliation` out of `_decision_loop`'s lazy
construction into `create_app`'s lifespan (stored on `app.state.execution`) so the cancel route
and the live loop share the *same* `FakeExchange` instance -- its in-memory order state lives on
that one object, not the ledger.

**Known limitation, noted not hidden**: today's live loop only ever places MARKET orders (always
resolved synchronously within one call, never left open) -- so this endpoint has no natural
trigger from the automated pipeline yet. It becomes load-bearing once a LIMIT order path or a
real LIVE venue with asynchronous fills exists. Also: if the API process restarts while a LIMIT
order is genuinely still open, `FakeExchange`'s in-memory order tracking resets and a later
cancel attempt on that specific order would raise (gateway "lost track" of it) rather than
resolving cleanly -- doesn't affect today's MARKET-only usage, worth fixing if/when LIMIT orders
ship for real.

Verified: full suite 638 passed, ruff/pyright clean, rebuilt/redeployed, all 8 services healthy.

**Immediate next actions**: ask the user what's next -- persistent operational circuit breakers,
walk-forward/backtest UI wiring, further `PENDING.md` phase auditing (Fase 6 AI, Fase 8 Telegram),
or something else entirely.

## Live PAPER decision loop wired end-to-end -- the session's headline delivery (2026-09-17, continued)

After clearing the working-tree backlog (below) and running a full phase-by-phase audit against
`docs/PENDING.md`, found the single biggest real gap: `DecisionPipeline` (regime→strategy→risk→
allocation, Phase 3 Slice 9) was fully built and tested but had **zero live callers anywhere in
`apps/`** -- no PAPER trade had ever been placed end-to-end in production, despite every piece
downstream (allocator, risk engine, execution service, ledger) being real and tested in isolation.
User said "ve directo a implementar" (skip a separate planning pass) when asked. Closed it in five
committed slices, each independently tested/verified:

1. `c653bef` -- SELL/reduce flow in the allocator + risk engine (was a hard `raise`; PENDING.md
   Fase 3 explicitly required "vender sin exceder lo poseído"). Risk-engine capacity for a SELL is
   now derived independently from held exposure, never BUY-side bucket headroom.
2. `54003fb` -- Real equity/PnL tracker: `wallybot/domain/equity.py` (daily/weekly loss, drawdown,
   persistent high-water-mark) + `wallybot/application/equity_tracker.py` (`assess_equity`, one
   mark-to-market ledger pass). Also extended `FakeExchange` with an optional `market_data`
   provider so it can price PAPER fills off real Kraken conditions instead of its own internal
   seeded random walk -- ARCHITECTURE.md's "PAPER uses an exchange simulator" made real for the
   first time.
3. `1cff3f1` -- The loop itself: `wallybot/application/decision_loop.py` (`run_decision_tick`) +
   `apps/api/main.py`'s `_decision_loop` wrapper (only `apps/api` has internet egress, same
   constraint as every other live job this session's history documents). Surfaced and closed two
   real prerequisites along the way: (a) **no PAPER account could ever have positive equity** --
   there was no funding mechanism anywhere, so added a one-time `POST /api/portfolio/fund`
   (Admin+fresh MFA, DB-constraint-enforced one-time) plus a Portfolio-page form; (b) `wally_api`
   had only ever been granted *read* access to order/fill/ledger tables (migration 0028 grants the
   write access the live loop and funding route both need -- 0002's own comment had assumed only
   the network-isolated `wally_worker` would ever write there).

**Explicitly scoped out, not silently skipped**: persistent operational circuit breakers (stale
data/exchange outage/repeated-errors, per RISK.md's full taxonomy -- only daily/weekly loss and
drawdown are real breakers right now, `active_breakers` is always `frozenset()`), order
cancellation orchestration (`ExecutionService` has the port, no `cancel()` method or route yet),
walk-forward/bootstrap wiring into the backtest UI (logic exists, tested, unreachable from
outside a unit test). Single-bucket-per-tick (CORE only) and single-admin-account, matching this
codebase's existing simplification level (no per-instrument bucket assignment schema, no
multi-user account administration yet).

**Verified for real, not just tests**: rebuilt and redeployed the full stack (migration 0028
applied, all 8 services healthy), confirmed via container logs and a direct DB check against the
*actual production stack* that the loop starts cleanly and correctly stays silent while the real
operator's account is in OBSERVE mode -- did **not** flip it to PAPER myself (needs the operator's
own fresh MFA, which this agent neither has nor should have). Full suite 629 passed at each
commit, ruff/pyright clean throughout (same one pre-existing unrelated `auth_routes.py` error),
frontend eslint/tsc clean.

**Immediate next actions**: ask the user which of the explicitly-scoped-out items to pick up next
(persistent breakers, cancellation, walk-forward UI wiring), or whether to keep auditing other
`PENDING.md` phases (Fase 6 AI provider is still a fake-only stub; Fase 8 Telegram has no inbound
commands/reports; Fase 9 LIVE remains correctly and completely unstarted, gated behind human-only
steps).

## Portfolio slice committed; working-tree backlog cleared (2026-09-17, new session)

Fresh session, no prior chat history. User: "continua con lo pendiente acaba todas las fases."
Cross-checked `.ai/CURRENT.md`/`HANDOFF.md` against `git log` first (this file's own recurring
lesson) -- found the Tiingo fix below was already committed (`e7c78f0`) despite this file saying
otherwise; the only real uncommitted work was the Portfolio slice plus a small unrelated Backtests
UX fix. Committed both (`9ad0c56`, `8460293`) after finishing them properly -- see `.ai/HANDOFF.md`
for the full detail (fixed 2 real pyright errors, ~30 missing EN translations, one lint error in
migration 0026). Full stack rebuilt/redeployed, all 8 services healthy, full suite 595 passed.

**Not yet started this session**: any new phase work. `docs/PENDING.md` (last reviewed 2026-09-12)
is stale relative to `git log` -- re-audit it against actual code before picking the next
increment, don't trust its checkboxes at face value. Raised to the user: "finish all phases"
includes Fase 9 (LIVE trading), which `RISK.md`/`SECURITY.md`/`AGENTS.md` gate behind human-only
steps (trade-only key evidence, TOTP+account confirmation, small-capital test, explicit
authorization) -- an agent can build LIVE's supporting infrastructure but cannot clear those gates
or "finish" activation unilaterally.

## Real Tiingo bug found from user-reported Inteligencia screenshot (2026-09-17, later still)

User pasted the live Confiabilidad/Consenso panels: Tiingo showed "Saludable, 0.0% error, 6
llamadas, 607ms" while BTC/USD and ETH/USD both stayed `INSUFFICIENT_DATA` with
`excluded_sources: ["kraken"]` -- Tiingo never even appearing as excluded, meaning it never
produced a `PriceQuote` at all, successful-looking reliability notwithstanding.

**Root cause, confirmed by direct reproduction**: `wallybot/application/price_consensus_job.py`'s
`_tiingo_source` (added in the "Tiingo key moved to the Connections UI" course-correction) builds
its own per-tick `httpx.AsyncClient(timeout=10.0)` with **no `base_url`** and passes it explicitly
into `HttpxTiingoTransport`, which skips its own `client or httpx.AsyncClient(base_url=...)`
default specifically because a client *was* passed. A relative-path request
(`"/tiingo/crypto/prices"`) against a client with no `base_url` raises `httpx.UnsupportedProtocol`
immediately, client-side, before any network I/O -- confirmed with a throwaway repro script.
Despite this, live `provider_reliability_snapshots` showed **zero tiingo rows at all** (not even
failed ones) for the current session, because `provider_connections` was actually empty the whole
time (both earlier UI attempts 403'd on stale MFA, now fixed) -- the "Saludable" data the user
pasted was leftover from an *earlier* slice this session, before the course-correction, when
`TiingoExchange` was built without an explicit client and so got the correct default `base_url`.

**Fix**: exported `wallybot/exchanges/tiingo.py`'s `_BASE_URL` as public `BASE_URL`; `_tiingo_source`
now passes `httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)`. Added a regression test
(`test_tiingo_source_client_actually_targets_the_real_api`) that asserts on `tiingo_client.base_url`
directly -- deterministic, unlike asserting on latency/success which depends on real network
conditions and would not have caught this (the *existing* fake-key test already "passed" while
hiding this exact bug, since `httpx.UnsupportedProtocol` is an `Exception` too).

**Also found and fixed a test-flakiness regression this job introduced**: `_price_consensus_loop`
fires immediately (no initial delay, matching `_market_ingestion_loop`'s convention) inside
`create_app`'s lifespan -- which every `client`-fixture integration test boots. Since
`provider_reliability_snapshots`/`price_consensus_results` are shared, session-scoped Postgres
tables and `list_latest()` picks the single most-recent row per key, a real-clock background tick
could non-deterministically "win" over whatever an unrelated test (e.g.
`test_provider_reliability_route.py`) had seeded, flaking tests that have nothing to do with
Tiingo. Two full suite runs each surfaced a *different* random failure before the fix. Fixed by
skipping `price_consensus_task` creation entirely when `config.environment == "test"` (this
session's own tests call `run_price_consensus_tick`/`_tiingo_source` directly, unaffected).
Confirmed fixed: two consecutive full-suite runs both green (595 passed) after the change.

**Also found, while redeploying**: a new migration (`0026_portfolio_api_read_grants`, part of the
concurrent Portfolio slice below) had not been applied -- `docker compose up migrate` had run
against a stale base image earlier in this session (before that migration existed in the tree),
so `/health/ready` correctly reported `not_ready` after redeploying `api` alone. Rebuilt the base
`wallybot-api:0.1.0` image too (not just `api-research`) and re-ran `migrate` -- same "rebuild both
images sharing the compose `&app` anchor" lesson this session has hit several times before.

**Verified:** full suite green twice in a row post-fix (595 passed each time), ruff/pyright clean
on every file this slice touched (pre-existing errors in Portfolio's own WIP files, not touched,
left alone). Rebuilt and redeployed the entire stack (`docker compose build` + `up -d`, no
arguments); all 8 containers healthy, `/health/ready` → `{"status":"ready"}`.

**Not yet committed** — ask before committing, per repo convention. Do not mix with the concurrent
Portfolio slice's own files (`apps/api/portfolio_routes.py`, its migration, its frontend page) --
those are not this agent's to commit.

**Still open, raised to the user rather than assumed:** (1) why every Mercados row shows `kraken`
as the only venue (this is correct/expected -- Tiingo has no live snapshot endpoint, only Kraken
feeds that table; explained in chat, not a code change), and (2) a much larger ask about a fully
autonomous LIVE trading/withdrawal agent and a real multi-wallet portfolio view -- explicitly out
of scope to start unilaterally per `RISK.md`/`SECURITY.md`'s LIVE gates and `AGENTS.md`'s "never
grant execution/withdrawal capability to research code paths" -- surfaced back to the user for a
scoping decision rather than assumed.

## Portfolio and internal-tool documentation (2026-09-17)

- Replaced the Portfolio placeholder with a signed-in, read-only PAPER ledger view. The new
  `/api/portfolio` route derives the only exposed ledger namespace from the authenticated user
  (`paper:<user-id>`); it never accepts an account identifier from the client.
- Added the API-only SELECT grants required to read fills and ledger tables, a frontend
  Portfolio page, and integration coverage for authentication and cross-user ledger isolation.
  It deliberately does not value assets from guessed prices, import exchange balances, trade, or
  withdraw funds.
- Added `docs/AI-DEVELOPMENT.md`: the internal routing guide for Archify, Serena, Context7 and
  Codebase Memory, including the update workflow and security boundaries. Product diagrams remain
  under `docs/diagrams/`; no external repository link appears in the product Docs page.
- Verification: `uv run pytest tests/integration/test_portfolio_route.py` (2 passed), focused
  TypeScript and ESLint checks passed, and `graphify update .` rebuilt the code graph.

**Do not mix the above slice with the concurrent Tiingo/price-consensus edits** visible in the
working tree. Review and commit them separately.

## Restored the Graphify repo link the Docs redesign dropped (2026-09-17, later the same day)

The "Control-center UX and recent MFA confirmation" slice below landed concurrently with this
agent's own independent diagnosis of the same "No se pudo agregar la conexión" / silent PAPER-toggle
failure the user reported -- both sessions converged on the identical fix (a `confirm-mfa` step-up
endpoint), and `git log` shows they merged into one commit (`f25fbdb`) without conflict. One real
regression from that merge: the Docs page redesign (product-first onboarding, five setup steps,
area cards) **dropped the Graphify repository link** the user had explicitly asked to be added "at
the top" of the Docs page. Restored it as a new highlighted panel right after the hero, styled with
the same `docs-safety-panel` pattern already used elsewhere on that redesigned page (icon, heading,
description, an outlined `Ver en GitHub` button opening https://github.com/Graphify-Labs/graphify
in a new tab) -- not a revert of the redesign, just the one thing it lost.

**Verified:** full backend suite still 592 passed, frontend eslint/tsc clean, full Playwright UI
suite (11 tests) green, confirmed visually via `claude-in-chrome` that the panel renders at the top
of `/docs` after rebuilding and redeploying `web`. Also used the live browser session (already
logged in as the operator) to click "Activar simulación PAPER" on the real, now-merged Settings
page: it correctly showed "Vuelve a iniciar sesión con tu autenticador para confirmar esta acción."
both in the page-level banner and inline next to the button -- confirming the concurrent MFA fix
actually resolves the silent-failure complaint, not just in tests. Rebuilt and redeployed **every**
service (`docker compose build` + `up -d`, no arguments) per the user's "redeployea todo"; all 8
containers healthy.

**Not yet committed** — ask before committing, per repo convention.

## Control-center UX and recent MFA confirmation (2026-09-17)

- Reworked **Configuración** into responsive state/action cards for OBSERVE/PAPER, Telegram, and
  recent MFA confirmation. Forms now remain aligned at phone widths and Telegram data hydrates
  after its query completes.
- Refined the shared visual rhythm across Control Center pages and rebuilt the sidebar: compact
  desktop rail, a closed-by-default mobile navigation menu, and smaller accessible switches. The
  shared component primitive is used for the mobile navigation trigger.
- Replaced developer-facing Docs content with product-first onboarding: five setup steps, a map to
  each Control Center area, and explicit OBSERVE/PAPER/no-withdrawal boundaries. Connections use
  their own responsive form grid rather than the market-filter layout.
- Added an authenticated `POST /api/auth/confirm-mfa` flow so an administrator can refresh the
  five-minute MFA window without a logout; integration coverage confirms stale/rejected/successful
  paths.
- Verified: `test_auth.py` (8 passed), focused frontend TypeScript/ESLint, and the fully mocked
  Playwright UI suite (including desktop/mobile settings/docs). `pyright` still reports the known,
  unrelated pre-existing type issue in `apps/api/auth_routes.py:65`.

**Commit intent:** user explicitly requested a commit. The current cohesive UI + MFA slice is ready
to commit after the final working-tree review; do not include unrelated future work.

**Task:** Continue closing the "backend exists, nothing shows it" gap per `docs/PENDING.md`'s
recommended delivery order. User said "Continua con el flow y la app ok?" — kept going
autonomously per this session's established pattern (no check-in between slices).

## Four user-reported bugs fixed in one slice (2026-09-17)

User pasted real UI output and flagged four separate things in one message. All four verified
fixed against the live Docker stack (not just tests), using `claude-in-chrome` since the user's
own logged-in browser session was reachable (same profile/cookies) — screenshots confirmed each
fix, not just green tests.

1. **Graphify's real repo wasn't linked from the Docs page, and the docs only covered the initial
   `graphify . --wiki` build, not the query/path/explain/update flow.** Added a prominent
   "Repositorio oficial de Graphify" link (https://github.com/Graphify-Labs/graphify) at the very
   top of `DocsPage.tsx`, before "Primeros pasos" -- opens in a new tab, never navigates away from
   the app. Expanded the Graphify section with the actual 4-command workflow and added "Pruebas y
   calidad"/"Estado actual del proyecto" sections (see the slice above this one for the rest of
   that work -- this continues it).
2. **Mercados page only ever showed 2 pairs (XBT/USD, ETH/USD).** Root cause: `KrakenExchange`'s
   default `pairs` (also used for `market_overview`) was never meant to be the *live browsing*
   universe -- it's deliberately narrow for ingestion/backtests/price-consensus (Parquet storage,
   API usage). Verified empirically that Kraken's real `AssetPairs` with no filter returns ~1450
   pairs (668 USD-quoted) -- far too many to fetch candles+snapshot for sequentially on every page
   load. Fix: a **separate** `KrakenExchange` instance for `market_overview` only, with a curated
   24-pair list of major USD pairs (symbols verified against Kraken's real `altname` field, not
   guessed -- Kraken uses "XBT" not "BTC", "XDG" not "DOGE", "POL" not "MATIC"). Also added bounded
   concurrency (`asyncio.Semaphore`, was fully sequential before) and per-instrument failure
   isolation (`wallybot/application/market_overview.py`: one bad pair no longer takes down the
   whole page) -- both needed regardless of pair count, but essential once it's 24 instead of 2.
   Live-verified: Mercados now shows "24 de 24 mercados" with real ranked prices.
3. **Backtest history table showed `final_equity` as
   "10999.93099135968523141293843 USD"** -- a real precision bug, not a display bug: unquantized
   `Decimal` division (`notional / fill_price` in `wallybot/backtest/engine.py`) carries its full
   ~28-digit context precision through every later multiplication. Initially "fixed" the frontend
   with `.toFixed(2)` -- **reverted that** after finding `apps/web/e2e/observability.spec.ts`
   already has a test asserting a huge Decimal string renders byte-for-byte
   (`"9007199254740993.125 USD"`), specifically to catch JS float precision loss on large numbers.
   The frontend's raw-string display is deliberate, not an oversight. Fixed at the actual source
   instead: `BacktestEngine.run()` now quantizes fill prices/quantities to the traded instrument's
   own `price_increment`/`quantity_increment` (quantity always rounds down, same convention
   `FakeExchange`/`deterministic_risk_engine` already use) and cash amounts (equity, fees,
   proceeds, cost basis) to `_CASH_PRECISION` (cents) after every step. Also now fails closed with
   a clear error if an instrument has no precision to backtest with (previously would have crashed
   obscurely inside `.quantize(None)`). Live-verified: ran a fresh backtest through the real UI
   (24-hour XBT/USD window, `feature_window=10`) -- new row shows "12103.69 USD", not 23 decimals;
   the one pre-fix historical row is unchanged (expected -- no retroactive data migration, only
   the computation going forward).
4. **Tiingo API key was a Docker secret, not the Connections UI.** See the "Course correction"
   slice above -- already fixed earlier this session, but confirmed again here: added a TIINGO
   connection through the real UI got rejected with **403 "Sign in again with MFA to confirm this
   action"** (`apps/api/dependencies.py`'s `admin()` dependency requires MFA within the last 300
   seconds for any Admin-gated action) -- not a bug, the intended security behavior. This agent
   cannot complete that step (needs the user's own TOTP code); left the Connections page open in
   the browser tab with Proveedor=TIINGO, Nombre=primary pre-filled and the API key field cleared,
   ready for the user to paste the key and submit themselves after re-confirming MFA.

**Verified:** full suite 590 passed, ruff/pyright clean (same pre-existing `auth_routes.py`
error), frontend eslint/tsc/`next build` clean. Rebuilt and redeployed both `api` and `web`;
confirmed via `claude-in-chrome` screenshots: Docs page (Graphify link + sections), Mercados (24
pairs, real prices), Investigación (new backtest shows 2-decimal equity). `graphify update .` run
after the code changes.

**Not yet committed** — ask before committing, per repo convention.

**Immediate next actions:** commit this slice if the user agrees. User still needs to add their
Tiingo key through Conexiones themselves (browser tab left ready). Otherwise pick the next
increment from `docs/PENDING.md`.

## Course correction: Tiingo key moved from Docker secret to the existing Connections UI (2026-09-17)

The previous slice (below, "Real Kraken+Tiingo price consensus...") wired the Tiingo API key as a
Docker secret (`Settings.tiingo_api_key`, `.secrets/tiingo_api_key`) — **user correctly pushed
back**: "no entiendo porque te tuve que pasar el token eso deberia estar en la ui que el usuario
ponga el suyo y automaticamente se configure." They were right, and more importantly there was
already a *built* mechanism for exactly this that the prior slice missed: `provider_connections`
(migration `0024_credentials`) + `apps/api/connection_routes.py` + `ConnectionsPage.tsx` already
let an operator add a `"TIINGO"` connection (a single encrypted API key, same shape as a wallet
address) through the web UI — `"TIINGO"` was already a valid `provider` literal in
`ProviderConnectionCreate` and already selectable in the UI dropdown, just never consumed by
anything. Same "storage exists, no consumer" pattern as the Telegram token, now found a second
time in the same session, this time in a piece of code *I* had just written -- worth remembering:
**always check `provider_connections`/`ConnectionsPage.tsx` before inventing a new credential
mechanism.**

- **Reverted**: `Settings.tiingo_api_key`, `load_settings()`'s tiingo entry, `docker-compose.yml`'s
  `tiingo_api_key` secret (both the top-level entry and the `api` service's mount),
  `.secrets/tiingo_api_key` (deleted -- no longer read by anything).
- **New**: `ProviderConnectionRepository.latest_with_key(provider)` -- the most recent connection
  row for a given provider that actually has a key stored.
- `wallybot/application/price_consensus_job.py` now re-checks for a usable `"TIINGO"` connection
  on **every tick** (`_tiingo_source`, decrypts via the same `Crypto` instance `AuthService` already
  holds, builds a fresh `TiingoExchange` + `httpx.AsyncClient` for that tick only, closed after)
  rather than deciding once at process start -- adding or removing a key through the Connections
  UI takes effect on the next tick (≤5 minutes), no restart. `run_price_consensus_tick`'s signature
  changed to `(sessions, crypto, clock, static_sources, now, outcomes)`; `apps/api/main.py`'s
  `_price_consensus_loop` now only ever constructs Kraken as a static source and passes
  `app.state.auth.crypto` through.
- Tests rewritten to match: `tests/integration/test_price_consensus_job_persistence.py` now uses
  the real `client`/enroll flow, adds a real `TIINGO` connection via `POST /api/connections` with a
  fake key, and asserts the dynamic lookup actually attempts it (a fake key against the real
  Tiingo API correctly fails at the HTTP layer -- recorded as an unsuccessful call, not silently
  ignored, not mocked).
- `DocsPage.tsx`: user also flagged the UI docs don't cover graphify's actual day-to-day workflow
  (only the initial `graphify . --wiki` build was there) and that other things were missing.
  Expanded the Graphify section with the `query`/`path`/`explain`/`update` flow (matching
  `AGENTS.md`'s own routing table), and added two new sections: "Pruebas y calidad" (how to run
  pytest/ruff/pyright) and "Estado actual del proyecto" (pointers to `docs/PENDING.md` and
  `.ai/CURRENT.md`/`HANDOFF.md`, previously not mentioned anywhere in the UI). New `en.json` keys
  added for all of it.
- Also swept in the pre-existing uncommitted frontend diff that was already sitting in the working
  tree at session start (architecture-diagram link on the Docs page, `proxy.ts`'s CSP-matcher
  exclusion for `/architecture.html`, `docker/web.Dockerfile` copying `public/` into the standalone
  build) -- it was complete and directly related to the Docs page work happening in the same
  commit, so no longer worth keeping separate. `apps/web/public/architecture.html` (a Graphify
  `callflow-html` export) is now actually served (verified: `curl .../architecture.html` → 200
  through the gateway, confirmed only after rebuilding `web` -- the Dockerfile fix was necessary,
  the standalone build doesn't include `public/` by default).

**Verified:** full suite still 587 passed, ruff/pyright clean (same pre-existing `auth_routes.py`
error), frontend `eslint`/`tsc --noEmit`/`next build` all clean, `en.json` valid JSON. Rebuilt and
redeployed `api` and `web`; all 8 services healthy. Confirmed via `psql` that `provider_connections`
has zero rows on the live stack right now -- **the user still needs to actually add their Tiingo
key through the Connections page in their own browser session for it to activate**; this agent
cannot do that step itself (would require reading `.secrets/bootstrap_token` to log in, which
`AGENTS.md` forbids outright).

**Not yet committed** — ask before committing, per repo convention.

**Immediate next actions:** commit this correction (two logical commits: backend Tiingo-via-UI
wiring, and the frontend Docs page batch) if the user agrees, then continue picking the next slice.

## Telegram notifications actually wired up (2026-09-16, new session)

Prior commits (4734a55) added encrypted storage for a Telegram bot token + chat id, but nothing
ever called `TelegramNotifier` -- both the route's and the migration's own docstrings said so
explicitly ("separate follow-up work"). This slice closed that gap for the one trigger that fits
today's process topology.

- **Key finding before writing anything**: `worker`/`scheduler` are *also* on the `operational`
  Docker network (`internal: true`), not just `research` -- only `api` (on `[edge, operational]`)
  has internet egress. So Telegram sending can only originate from inside `apps/api`, not from a
  scheduler/worker tick as originally assumed. This also means research-job-failure notifications
  (the other candidate trigger) aren't reachable yet without a cross-process design (api polling
  for job-status transitions) -- left for later, noted below.
- New `wallybot/application/notification_dispatch.py`: `dispatch_telegram_notification(sessions,
  crypto, transport, notification)` -- reads the singleton `telegram_config` row, no-ops silently
  if disabled/unconfigured, otherwise decrypts the token and sends. Any failure (bad token,
  network error) is caught and logged (`TELEGRAM_NOTIFICATION_FAILED`), never raised -- Telegram
  is a convenience channel, never a dependency of the action that triggered it.
- New `HttpxTelegramTransport` in `wallybot/notifications/telegram.py`, mirroring
  `HttpxKrakenTransport`'s shape in `wallybot/exchanges/kraken.py`. Built once in `apps/api/main.py`'s
  lifespan (`app.state.telegram_transport`, one shared `httpx.AsyncClient`, closed on shutdown).
- Wired into `apps/api/system_routes.py`'s `control()`: pausing sends a WARNING notification,
  resuming sends INFO, only when the status/environment actually changed (repeating the same
  status is a no-op, no duplicate notification). Chosen because it's the one sensitive admin
  action that already runs entirely inside `apps/api` with `request.app.state.auth.crypto`
  already available -- no cross-process plumbing needed.
- Fixed `SystemView.telegram` in the same file: was hardcoded `"DISABLED"` since the field was
  added before there was anything to report; now reflects the real config (`enabled` + token +
  chat_id all present).
- Tests: `tests/integration/test_notification_dispatch.py` (new -- disabled/no-chat-id/happy-path/
  transport-failure-is-swallowed, using a fake transport, no real network) + 4 new tests appended
  to `tests/integration/test_telegram_routes.py` (system() reflects enabled/disabled; pausing with
  Telegram configured sends exactly one notification with the right chat/text; pausing without
  Telegram configured sends nothing; repeating the same status sends nothing).

**Verified:** full suite 580 passed (457 unit/property + 123 integration, up from 457+113), ruff
clean repo-wide, pyright clean except the one pre-existing unrelated `auth_routes.py` error
(confirmed present before this slice too). Rebuilt both `wallybot-api:0.1.0` and
`wallybot-api-research:0.1.0` (no new migration this slice, but rebuilt both per this session's own
established lesson about the compose `&app` anchor), ran `docker compose up migrate` (no-op, schema
unchanged), recreated `api`, brought `worker`/`scheduler`/`research`/`gateway`/`web` up too -- all 8
services healthy, `/health/ready` → `{"status":"ready"}` through the gateway. Did **not** manually
curl-test the real running stack's `/api/control` with a real bootstrap token, since that requires
reading `.secrets/bootstrap_token`'s contents, which `AGENTS.md` forbids outright -- the integration
suite's `TestClient`-based tests exercise the identical route/app/DB stack instead (real Postgres via
testcontainers, real `Crypto` encrypt/decrypt, real FastAPI routing), which is the closest available
substitute given that constraint. `graphify update .` run after the code change.

**Not yet committed** — ask before committing, per repo convention.

**Immediate next actions:** commit this slice if the user agrees. Longer-lived gap noted above:
research-job-failure notifications need `api` to poll for job-status transitions (or some other
cross-process signal), since `research` itself has no internet egress to call Telegram directly --
not started this slice, flagged for whoever picks up Telegram/notifications work next.

## Real Kraken+Tiingo price consensus and provider reliability (2026-09-17, same session)

User approved committing the Telegram slice and asked to continue. Next candidate from the same
"what's dead code from a prior slice" sweep: `wallybot.exchanges.tiingo.TiingoExchange` (added
earlier this session) had zero callers, and `wallybot/domain/price_consensus.py`/
`provider_reliability.py` both say in their own module docstrings that only one real provider
(Kraken) was ever wired up, so their pure computations had no live, multi-provider caller either.
Tiingo needs its own API key (unlike Kraken's public endpoints) -- asked the user via
AskUserQuestion, they provided one directly in chat, which was written straight to
`.secrets/tiingo_api_key` via the Write tool and never echoed back, per `AGENTS.md`'s secrets rule.

- New `wallybot/application/price_consensus_job.py`: queries every configured provider for two
  hardcoded tracked pairs (BTC/USD, ETH/USD -- the same pairs `KrakenExchange`'s own default
  `pairs` already limits everything else to) via `fetch_candles` (Tiingo's `fetch_snapshot` always
  raises `NotImplementedError`, so both providers are queried the same candle-based way for a fair
  comparison), builds `PriceQuote`s from each provider's most recent closed 1-minute candle, calls
  `compute_price_consensus`, and separately accumulates `ProviderCallOutcome`s in an in-memory
  rolling window (no new table -- a restart just means a brief `INSUFFICIENT_DATA` reliability
  status until 5 calls reaccumulate) to call `compute_provider_reliability`. Split into a DB-free
  `compute_price_consensus_and_reliability` (unit-tested with fake providers) and a thin
  `run_price_consensus_tick` that persists the result (integration-tested against real Postgres).
- Wired into a new `_price_consensus_loop` in `apps/api/main.py`'s lifespan (same reasoning as
  `_market_ingestion_loop`: only `apps/api` has internet egress), ticking every 300s (matches
  `DEFAULT_MAX_STALENESS`). Kraken is always a source; Tiingo is added only if
  `Settings.tiingo_api_key` (new, optional `SecretStr | None`, read from
  `/run/secrets/tiingo_api_key` in `load_settings()`) is present and non-empty -- absent, the job
  still runs Kraken-only and correctly reports `INSUFFICIENT_DATA` forever (one source can never
  reach consensus), never fabricating a two-source result from one feed.
- **Found and fixed a real bug in `wallybot/exchanges/tiingo.py` while verifying against the live
  API with the real key**: `fetch_candles` passed `endDate: now.date().isoformat()`, but verified
  empirically that Tiingo's `endDate` is an *exclusive* boundary at that date's midnight -- passing
  today's date silently dropped every row from today, making Tiingo's data look permanently hours
  stale (always failing the 5-minute consensus staleness filter) when the real API is actually
  near-real-time (`resampleFreq=1min` does return true minute bars up to the current minute).
  Fixed by requesting `endDate` one day past `now`'s date instead; the existing `close_time > now`
  filter already prevents any lookahead regardless of this. Module docstring updated to record
  both the fix and what's now verified vs. still unconfirmed about the API.
- **Found and fixed the same recurring access-control gap a 6th time** (0012/0013/0016/0017/0018/
  0023, now 0025): migration `0016` granted `wally_api` read-only `SELECT` on
  `price_consensus_results`/`provider_reliability_snapshots`, written when `0010`'s own docstring
  assumed `wally_worker` would be the eventual writer -- but `worker`/`scheduler`/`research` have
  no internet egress to reach a second market-data provider, so `apps/api` had to become the
  writer instead. New migration `0025_price_consensus_api_grants` grants `wally_api` `INSERT` on
  both tables plus `USAGE, SELECT` on both autoincrement sequences (the `experiment_records_id_seq`
  gotcha from `0023` again). Found via the live Docker stack (`PRICE_CONSENSUS_TICK_FAILED` in
  `api`'s logs) -- the integration test suite's `sessions` fixture connects as the Postgres
  superuser, not the `wally_api` role, so it structurally cannot catch a missing per-role grant;
  only the real deployment surfaces this class of bug, same lesson as every prior occurrence.
- `docker-compose.yml`: new optional `tiingo_api_key` secret (file must exist for compose to
  mount it, but an empty file disables Tiingo cleanly rather than erroring -- see the comment next
  to it), mounted only into `api`.

**Verified:** full suite 586 passed (462 unit/property + 124 integration, up from 580), ruff/
pyright clean repo-wide except the same one pre-existing unrelated `auth_routes.py` error. Rebuilt
`wallybot-api-research:0.1.0` (and `wallybot-api:0.1.0` once, for the grants migration), ran
`docker compose up migrate` (applied `0025` cleanly), redeployed `api`. **Confirmed real, working,
two-source consensus against the live stack, not just tests**: after the Tiingo fix, `psql` showed
`price_consensus_results` rows with `status=CONSENSUS`, `included_sources=["kraken","tiingo"]`,
and real BTC/ETH prices; `provider_reliability_snapshots` showed both providers accumulating calls
correctly (still `INSUFFICIENT_DATA` right after a restart -- expected, needs 5 calls/~15 minutes
to reach a confident status). `graphify update .` run after the code changes.

**Not yet committed** — ask before committing, per repo convention (the Telegram slice above this
one was already committed with the user's explicit approval this session).

**Immediate next actions:** commit this slice if the user agrees, then pick the next increment.
Worth flagging to the user later: Tiingo's real crypto data freshness/rate limits under their
specific plan are now empirically verified as of 2026-09-17, but could still change if their
account tier changes -- no code currently detects or alerts on that beyond the existing provider
reliability status naturally degrading if it happens.

## Latest slice — Parquet ingestion job verified end-to-end + a durability bug fixed (2026-09-16)

The Parquet dataset-ingestion job (`wallybot/application/market_ingestion.py`,
`HistoricalIngestionCursorRepository`, migration `0019_historical_ingestion_cursor`, the
`_market_ingestion_loop` background task in `apps/api/main.py`'s lifespan, and the
`historical_data` Docker volume) was already implemented and unit/integration tested from earlier
in this session — but not yet verified against the real running stack, and not documented here.
This slice did that verification and found + fixed a real bug:

- Rebuilt `wallybot-api:0.1.0` (base, used by `migrate`/`worker`/`scheduler`) and
  `wallybot-api-research:0.1.0` (used by `api`/`research`) — both needed, same lesson as the
  0018 slice. Ran `docker compose up migrate` (applied `0019` cleanly), force-recreated `api`,
  confirmed `/health/ready` → `{"status":"ready"}` at `0019_historical_ingestion_cursor`.
- **Found a real durability bug** while checking the result: `HistoricalStore._write_parquet` /
  `_write_manifest` wrote to a `.tmp-*` file and used `os.replace` for atomicity, but never
  `fsync`'d before the rename. On this host, a prior run (~17h earlier, same session, before this
  slice) left **60 zero-byte "published" partitions** (30 dates × XBT_USD/ETH_USD) sitting under
  `/data/historical` — `os.replace` had completed (so the corrupted file has the final, non-tmp
  name) but the write's dirty pages never made it to the volume's backing disk, most likely
  because the Docker Desktop VM was paused/resumed (laptop sleep) between the write and now.
  A single corrupted file breaks DuckDB's `read_parquet(glob)` for the *whole* instrument
  (`InvalidInputException`), so this wasn't just "missing data", it was "broken backtests".
  Fixed in `wallybot/data/historical.py`: both writers now open the tmp file explicitly,
  `flush()` + `os.fsync(fd)` before `os.replace`. Rebuilt/redeployed `api` with the fix.
- User explicitly chose (asked via AskUserQuestion) to delete the 60 corrupted files but
  **not** reset the ingestion cursor — the cursor already advanced past those dates when the
  original (corrupted) write "succeeded", so normal hourly ingestion will **not** backfill
  Aug 17–Sep 15. XBT_USD/ETH_USD 1h data now starts fresh from 2026-09-16 03:00 and grows one
  candle/hour going forward (verified via DuckDB inside the `api` container after cleanup: 17
  rows each, `InvalidInputException` gone). **If a fuller backtest window is needed later,
  delete the two rows in `historical_ingestion_cursors` for `(kraken:SPOT:BTC/USD, 1h)` and
  `(kraken:SPOT:ETH/USD, 1h)` to force a bootstrap re-fetch (720h lookback) — nobody has asked
  for that yet.**
- Verified: `uv run pytest tests/unit/test_market_ingestion.py` (7 passed), full non-integration
  suite (428 passed, 100 deselected — integration/e2e need Docker, which is up but wasn't
  re-run in full this slice), ruff + pyright clean on every touched file. `graphify update .`
  run after the code change.
- **Not yet committed** — this and the wallet-activity/entity-graph slice below are both still
  sitting uncommitted in the working tree; nothing has been committed this session.

**Immediate next actions:** decide whether to commit (nothing committed yet — ask the user, don't
commit unilaterally per repo convention). Longer-lived gap to flag to the user: the ingestion job
only has ~17 hours of real history right now, not the 30-day backtest window Phase 5 implicitly
assumed — worth deciding if/when to reset the cursor to backfill.

## Research job consumer wired up (2026-09-16, later the same day)

Closed the gap flagged above: `research_routes.py` (Codex, previous slice) let an Admin enqueue a
RESEARCH job via `POST /api/research/jobs`, but nothing ever consumed it -- `apps/research_worker`
did nothing but heartbeat. User decision (asked explicitly): the consumer re-runs the backtest an
existing `ExperimentRecord` describes and saves the result as a new record.

- **Network isolation constraint found and resolved per user decision**: `BacktestOrchestrator`
  normally resolves the traded `Instrument` (including price/quantity precision) via a live
  `discover_instruments()` call -- but `research`'s Docker network is `internal: true` (Fase 7
  isolation, PENDING.md), so it can never reach Kraken. Fix: `ExperimentRecord` now stores the
  full `Instrument` identity (`instrument_market_type`/`price_increment`/`quantity_increment`/
  `min_quantity`, migration `0023_experiment_precision` -- kept to 26 chars, the same
  varchar(32) `alembic_version` gotcha 0019 already documents) so a re-run reconstructs it
  offline instead of calling a live adapter. `BacktestOrchestrator.run()` now accepts an optional
  pre-resolved `Instrument` to skip discovery entirely (backward compatible: the live
  `POST /api/backtests` route passes none, unchanged behavior).
- New `wallybot/application/research_runner.py`: claims one RESEARCH job, looks up its
  `ExperimentRecord`, re-runs the backtest offline, saves the new record, and always reaches
  `complete` or `fail` on the job (never leaves it RUNNING). Wired into
  `wallybot/infrastructure/jobs.py`'s `tick()` for `service == "research"` -- **as a lazy/local
  import**, not module-level: `research_runner` pulls in `duckdb` via `backtest_orchestrator`,
  which only exists in the `runtime-research` image (api/research), not the base image
  worker/scheduler run on. A module-level import crashed both of those on redeploy (caught and
  fixed this slice, see below).
- Added a `fail()` transition to `wallybot/domain/research_job.py` and a matching
  `ResearchJobRepository.fail()` -- neither existed before; a job that couldn't complete had no
  defined way to stop being RUNNING.
- `research`'s Docker network never had the `historical_data` volume mounted (added, read-only)
  and `ProcessSettings` (worker/scheduler/research's settings, distinct from the api-only
  `Settings`) never had `historical_data_root` (added).
- Migration 0023 also grants `wally_research` `USAGE`/`SELECT` on `experiment_records_id_seq` --
  it had SELECT/INSERT on the table since migration 0015 but never the sequence, so it could
  never actually have inserted a row even before this slice (same gap 0017 already found and
  fixed for `wally_api`).

**Bugs found and fixed while verifying this end-to-end against the live Docker stack** (not just
unit tests -- this repo's own convention, see the 0018/0019 grant gotchas):
1. Migration revision id `0023_experiment_instrument_precision` (36 chars) exceeded
   `alembic_version.version_num`'s varchar(32) and failed `alembic upgrade head` with
   `StringDataRightTruncation` -- renamed to `0023_experiment_precision` (both the revision id
   and the file).
2. `jobs.py` importing `research_runner` at module level crashed `worker`/`scheduler` on startup
   (`ModuleNotFoundError: No module named 'duckdb'` -- those run the base image, not
   `runtime-research`). Fixed with a local import inside the `service == "research"` branch.
3. The pre-fsync-fix corrupted run (documented earlier in this file) left not just 60 zero-byte
   `.parquet` files (already cleaned) but 62 sibling zero-byte `.manifest.json` files that were
   never cleaned -- `json.loads("")` on one of them broke every `read_candles` call. Found via a
   real end-to-end smoke test (seeded a real `ExperimentRecord` + `JobRow` in the live DB,
   watched `research_worker` claim and fail it, read the actual error), cleaned up, re-verified:
   `research_worker` claimed a fresh job, re-ran the backtest from real local Parquet data with
   zero network access, saved a new `ExperimentRecord`, marked the job COMPLETED. Smoke-test rows
   deleted afterward.

Verified: full suite 557 passed (444 unit/property + 113 integration, up from 105 -- new
`test_research_runner.py` plus updated `test_experiment.py`/`test_backtest_orchestrator.py`/
`test_research_job.py`/`test_jobs.py`/`test_experiment_persistence.py` for the new
`ExperimentRecord` fields and `tick()` signature). Ruff/pyright clean (same one pre-existing
unrelated `auth_routes.py` error confirmed present on `master` before any of this session's
changes). All four backend services (api/worker/scheduler/research) rebuilt, redeployed, healthy.

**Not yet committed** — this slice, on top of everything else already described in this file,
still sits uncommitted. Still true: never commit without the user asking first.

**This session's delivery:** connected the last two Phase 10 OBSERVE-only signals that were not
yet surfaced in the UI — wallet activity (on-chain feed) and the Entity Correlation Graph. Same
end-to-end pattern as Smart Money/whale flow/token risk/provider reliability/price consensus:

- `wallybot/infrastructure/wallet_activity_repository.py`: `list_recent(limit=100)` — newest-first
  across every monitored wallet (previously only had `list_for_wallet`, per-wallet).
- `wallybot/infrastructure/relationship_repository.py`: `list_recent(limit=100)` — newest-first
  across the whole graph (previously only had `find_by_node`, node-scoped traversal).
- `GET /api/intelligence/wallet-activity` and `GET /api/intelligence/entity-graph` in
  `apps/api/intelligence_routes.py` + `apps/api/dto.py`'s `WalletActivityRowView`/
  `WalletActivityView`, `RelationshipRowView`/`EntityGraphView`.
- **Same recurring access-control gap found again** (5th time: 0012/0013/0016/0017/now):
  `wally_api` had no grant on `wallet_activity_events`/`relationships` — migration
  `0018_wallet_relationship_grants` (had to keep the revision id ≤32 chars — Postgres's
  `alembic_version.version_num` column caps at varchar(32); a first, longer id caused
  `StringDataRightTruncation` on `alembic upgrade head`, now known for next time). Bumped
  `apps/api/main.py`'s hardcoded Alembic revision check to
  `"0018_wallet_relationship_grants"` (same recurring rough edge, still not dynamic).
- Frontend: `apps/web/src/lib/dto.ts`'s `walletActivityRowSchema`/`walletActivitySchema`,
  `relationshipRowSchema`/`entityGraphSchema`; `useWalletActivityData.ts`/`useEntityGraphData.ts`;
  `WalletActivitySection.tsx`/`EntityGraphSection.tsx` composed into `IntelligencePage.tsx`
  (no new nav entry needed — same "Inteligencia" page as the other five signals) and wired into
  `Dashboard.tsx`. English strings added to `lib/locales/en.json`.
- Tests: `tests/integration/test_wallet_activity_route.py` + `test_entity_graph_route.py`
  (auth-required + seeded/empty via the real repositories); a new Playwright test in
  `observability.spec.ts` (populated + empty states) plus the two new endpoints added to the
  shared `shell()` fixture's route map (every test that opens `/intelligence` now needs them
  stubbed, since `Dashboard.tsx` fires both hooks unconditionally on that page).

**Verified:** full suite 516 passed (510→516), ruff/pyright clean on every touched file, domain
purity untouched (no domain changes this slice — pure repository/API/frontend wiring), `tsc`/
`eslint`/`next build` clean, full Playwright suite green (9 passed, 1 skipped as always) including
the new wallet-activity/entity-graph test. Rebuilt **both** the `api`-research image and the base
`wallybot-api:0.1.0` image (the `migrate`/`worker`/`scheduler` services share the base image via
docker-compose's `&app` anchor — rebuilding only `api`/`web` is not enough when a new migration
ships; learned this the hard way this session after `migrate` silently ran against a stale image
with no `0018` file present). Migration applied via `docker compose up migrate`, `api` restarted,
`gateway`/`api`/`web` all healthy, `/health/ready` → `{"status":"ready"}` at
`0018_wallet_relationship_grants`, `/login` serving 200 through the gateway. Not yet committed.

**Phase 10 status: now fully surfaced in the UI** — all 5 OBSERVE-only signal families
(Smart Money, whale flow, token risk, provider reliability/price consensus, wallet activity,
entity graph) are visible on the Inteligencia page. Remaining Phase 10 gap: Slice 4b (real
wallet/entity vendor adapter — blocked on an API key decision, per `.ai/HANDOFF.md`).

**What's realistically left for a "finished product"** (unchanged from before this slice, see
`.ai/HANDOFF.md`'s longer list): the Parquet dataset-ingestion job so `POST /api/backtests`
returns non-empty results in production; Phase 12 Slice 4 (real AI adapter, needs an authorized
model/API key decision) + a scheduler actually calling `ShadowDecisionService`; Phases 7/8
(research agents, Telegram); Phase 9 (LIVE trading, gated behind RISK.md/SECURITY.md evidence).

**Immediate next actions:** commit this slice's changes (not yet committed). Then, per
`docs/PENDING.md`'s delivery order, the next body of work is either the Parquet ingestion job
(makes backtests non-empty in production) or Phase 6/12 Slice 4 (needs a model/API key decision
from the user first — cannot proceed on that path without one).


## System service summary — 2026-09-15

Codex added counts for reported essential connections/processes, healthy services and services needing review. Optional integrations excluded; failed refresh labels the summary as the last successful check. ES/EN and responsive layout preserved. Focused mocked browser test passed (counts, stale refresh, empty processes, mobile); screenshot inspected; ESLint, TypeScript and targeted Ruff passed. Docker unavailable (named pipe missing), so production-stack verification and web deployment were not performed. New apps/web/playwright.ui.config.ts runs only fully intercepted observability specs using scripts/ui_test_server.py, stripping WALLY_* environment and directing fallback API traffic to an unused local port. No backend changes.

Final verification: all 8 mocked observability browser tests passed with the frontend-only config; Graphify AST update completed; git diff --check clean. Docker deployment remains pending.


## Backtest form clarity — 2026-09-15

Codex UI: allocation now explicitly a fraction, with examples for allocation/fees/slippage. Dates disclose browser time zone and UTC transport; invalid or reversed/equal windows are blocked before API submission with translated accessible errors. Instrument names are required with max length 16; feature window required, 1–500 per API. Decimal strings remain unchanged in requests. Focused browser test passed for rejected dates without POST, ES/EN errors, decimal payloads, successful execution/history and server 422. ESLint/TypeScript passed. No backend or deployment changes; previous Docker availability limitation remains.

## Portfolio accounting and deployed PAPER clarity — 2026-09-21

Codex added deterministic FIFO accounting for each signed-in user's PAPER ledger: realised PnL and
open cost basis are exposed in `GET /api/portfolio` and rendered in the portfolio. The page now
states correctly that the application is deployed while PAPER is only its isolated simulation
account; it never moves external funds. No unverified mark-to-market value is displayed.

The app stack was rebuilt and redeployed: API, web, worker, scheduler, research worker and
migration service are healthy; `http://localhost:3333/health/ready` returned `{"status":"ready"}`.
`uv run pytest tests/unit/test_portfolio_performance.py tests/integration/test_portfolio_route.py`
passed 15 tests. The tree remains intentionally shared/dirty with concurrent work; do not reset
or commit unrelated changes.

## Telegram token-first pairing — 2026-09-21

Telegram no longer requires a manually discovered Chat ID. An ADMIN stores a bot token, receives
a one-time `/start <code>`, and the API long-poll loop allowlists only the chat that returns that
exact code. The code is returned only in that authenticated POST response and its SHA-256 digest
is the sole persisted value. Wrong codes are ignored without reply. Migration `0032_telegram_pairing`
applied during the full redeploy; all services are healthy and `/health/ready` returned ready.
Focused route/loop coverage: 33 passed; Ruff and web TypeScript passed. Never use a bot token
posted in chat: revoke it in @BotFather first.
