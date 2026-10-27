## Container verification and scanner repair — 2026-10-27

Hosted run 40547639825 passed 1,146 Python tests, both browser suites, typing, lint,
Bandit, Python/frontend dependency audits, all Compose image builds, service readiness,
and encrypted backup creation/restore verification. The local full suite passed 1,154
cases with 91% coverage after the shutdown fix; the real-child lifecycle regression passed.
Graphify's local AST index was updated (5,111 nodes / 14,759 edges).

The remaining hosted failure occurred before image analysis: trivy-action v0.33.1 could
not install its default Trivy v0.65.0 binary. Update the action to v0.36.0 and explicitly
select official Trivy v0.76.1. HIGH/CRITICAL failures and all five image gates remain enabled;
no vulnerabilities are suppressed. Image scan results require the next hosted run.

## Intermittent API shutdown repair — 2026-10-27

Hosted run 40545572416 isolated the Python hang to TestClient shutdown in
`test_shared_throttle_fails_closed`, immediately after a heartbeat metrics tick failed.
The API awaited the infinite metrics task after a one-shot cancellation request.
The metrics loop now observes an explicit shutdown event before restarting or sleeping;
shutdown sets the event before requesting cancellation. This also wakes an idle metrics loop.
No authentication, risk, execution or portfolio calculation behavior changed.

A bounded real-child regression repeatedly opens and closes the API twenty times against the
fixture PostgreSQL/Redis services; captured child output and disposable credentials are not
printed. The preceding hosted run passed all 1,145 Python tests, development and production
browser suites and Bandit; it exposed the separately repaired msgpack audit finding.
Hosted Docker readiness, backup and Trivy still require a successful follow-up run.

## Hosted CI follow-up — 2026-10-27

The initial repaired Foundation run and its retry timed out in Python integration startup.
The log did not identify the blocked operation; do not treat that as an application failure
or claim a confirmed root cause. CI now pulls the PostgreSQL and Redis images explicitly,
prints each Python test and its live setup output, dumps a stack after 60 seconds, and bounds
the Python step to eight minutes. The existing full suite and all later gates remain enabled.

EXECUTED: 758 local unit/contract tests and four PostgreSQL/Redis integration tests passed.
Hosted run 40543736500 passed 1,145 Python tests with coverage, frontend lint/build,
22 development browser tests (one production-only skip), 23 production browser tests and Bandit.
Its pip-audit gate then found CVE-2026-114613 in msgpack 1.2.2; the lockfile now selects
msgpack 1.2.4. Compose readiness, backup verification and Trivy remain unverified on this head.
Local pytest reported a non-fatal cache-directory permission warning.

## CI gate repair — 2026-10-27

The failing Foundation checks stopped at Ruff formatting. Follow-up validation exposed
optional-value typing errors, a service-worker lint environment gap, stale vulnerable
dependencies, incomplete disposable browser-test setup, and a missing LIVE positions fixture.

- Normalize Python formatting; add explicit runtime guards where assertions or optional values
  previously hid invalid states. No trading calculations, limits or approval rules were changed.
- Keep the gitignored, separately managed Rust Discord bot out of WallyBot's Pyright scope.
- Update certifi/filelock/urllib3, Next.js and Zod and refresh affected transitive lock entries.
  Both pip-audit and pnpm audit now report no known vulnerabilities. No audit findings are ignored.
- Preserve strict CSP: shared Zod interpreter configuration disables its dynamic-code probe;
  production browser tests still reject unsafe-eval/unsafe-inline and every policy violation.
- Create disposable DB roles before browser migrations and use the restricted API role afterward.
  Fresh-install bootstrap now generates the AI credentials expected by Compose, and a real
  child-process/file regression test verifies first creation and refusal to overwrite an install.
- Review Bandit false positives only at seeded simulation, public enum-label and argv-only
  transport sites, with local rationale; replace production assertions with explicit guards.

EXECUTED: Ruff lint/format, Pyright (zero errors), Bandit, both dependency audits, frozen
Python/frontend installs, frontend lint/build, full Python suite (1,152 passed), 92 focused
regressions, the new bootstrap regression (1 passed), and production browser suite (23 passed).
The development browser suite passed 22 tests; its production-only case was intentionally skipped. Hosted Docker image builds,
readiness, backup verification and Trivy retain their existing mandatory CI gates; local
production deployment, live exchange operations and model inference were NOT EXECUTED.

# Gross market references — 2026-10-14

Final focused unit/integration run: 69 passed in 54.19s with disposable PostgreSQL/Redis. Includes
hand-calculated BTC/ETH/50-50 returns, nominal cash, unavailable boundaries, source/quote/venue
mismatch, duplicates, future evidence, overflow, UTC midnight, report context and line breaks,
legacy USD/XBT compatibility and existing Binance/Telegram controls. Scoped Pyright zero errors;
Ruff and diff whitespace clean. Public Binance and final deployed read-only report preview
returned all 4 references available; no message dispatched. API rebuilt; eight services healthy,
readiness 200, production OBSERVE with zero orders/fills. No frontend/schema changes.
Net account outperformance/cash-flow-adjusted comparisons are not covered or claimed delivered.

# Telegram report accuracy — 2026-10-14

50 focused unit/integration tests passed in 29.23s using disposable PostgreSQL/Redis. Coverage:
Spanish report text without internal phases, truthful reconciliation, actual OBSERVE/LIVE mode,
Binance account/USDT/LIVE fees, foreign-owner isolation and existing Telegram commands. Pyright,
Ruff and diff whitespace clean. API image rebuilt; no frontend/schema changes. No real trade or
manual Telegram test delivery. Benchmark comparison remains unavailable, explicitly disclosed.

# Binance migration verification — 2026-10-12

Final backend run: 1046 passed in 201.46s, including unit/property/contract and real PostgreSQL/
Redis integration. Production browser run: 21 passed (1.1m); final mocked browser run: 19 passed
(41.3s). Pyright, frontend tsc and scoped ESLint, Ruff and git diff whitespace checks passed.
Regression coverage: Binance USDT price/reliability calls without USD mixing; cash context labels;
LIVE venue reporting; PAPER USDT funding/approval without private submission; cross-account fill
identities; IOC/price/trade evidence and quote totals; cash excluded from LIVE positions.

Real public API: 23 curated Binance instruments, valid BTC/USDT and ETH/USDT bid/ask and 29
closed hourly candles in a 30-hour lookback. Backup isolated restore verified before applying
0046; images rebuilt sequentially after Docker recovery. Eight services healthy, readiness 200,
native heartbeat and first two-instrument analysis tick verified. Production OBSERVE, no LIVE
account configured, zero orders/fills. Funded Binance key/order acceptance remains untested.
Third-party deprecations and Windows pytest-cache permission warnings remain.

# Operator-readiness fixes — 2026-10-12 (second pass)

971 backend tests passed in 145.82s (unit/property/contract/integration, real PostgreSQL/Redis via
Testcontainers). Production-mode browser suite: 19 passed in 45.9s (`WALLY_E2E_PRODUCTION=1 pnpm
test:e2e`). Mocked UI suite (`playwright.ui.config.ts`): 17 passed. Scoped Pyright (apps/api,
apps/ai_worker, wallybot): 0 errors. New regression coverage: closed-candle lookback reaching the
analysts, analyst availability reporting/privileges/API, Kraken error explanations, malformed
secret, LIVE activation with a rejected key, local limit validation and signed-out guidance in
Settings. Pre-deploy encrypted backup restore verified (revision 0044, row counts recorded).

# Real spot verification â€” 2026-10-12

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

# WallyBot PAPER verification â€” 2026-10-08

Final local verification: 911 unit/property/contract/integration tests passed in 143.21s,
using real disposable PostgreSQL and Redis. Final production Playwright suite: 17 passed
in 42.6s, including setup/login/MFA/recovery and production nonce/CSP assertions. Feature
browser scenarios use mocked responses; order persistence, FIFO results, owner isolation,
Telegram review-only behavior and database role restrictions are covered by integration tests.
No real-money execution or performance claim is made.

WallyBot-scoped Pyright: zero errors. Ruff, frontend TypeScript and focused ESLint passed.
Eight deployed Compose services healthy; readiness 200; migration 0041 applied. API/native
analyst restart preserved production counts (zero orders/fills before and after). Real Codex
and Claude HOLD checks, Telegram getMe and public Kraken quotes succeeded. Analysis remains
disabled pending operator MFA activation. See [native analyst runbook](../runbooks/native-ai-worker.md).

Integration startup skips external market ingestion; ingestion job tests call the job directly.
Dependency deprecations and a non-fatal Windows pytest-cache permission warning remain.
These local results do not certify remote CI or the broader LIVE/multi-provider roadmap.

# Foundation verification

Recorded 2026-09-10 (America/Mexico_City), on Windows with Python 3.12.14 and Docker Desktop Linux containers.

| Check | Result |
| --- | --- |
| pytest unit/property/integration | 23 passed; no skipped integration tests |
| PostgreSQL / Redis | Real Testcontainers instances, PostgreSQL 17.11 and Redis 7.4.11 |
| Auth coverage scenarios | Setup race, TOTP replay/concurrency, recovery login, session expiry/revocation, CSRF, origin rejection, input redaction |
| Authorization | Real API role grants; VIEWER denied writes; research denied identity/control access and heartbeat spoofing; audit deletion denied |
| Failure behavior | Unavailable DB/Redis yields not-ready; liveness remains available; Redis outage blocks login |
| Jobs | Concurrent scheduler deduplicates; workers apply maintenance once; future/unknown jobs stay pending |
| Browser | Chromium setup/login/dashboard/pause/resume/events/system/logout/recovery flow; desktop/mobile visual inspection |
| Static checks | Ruff, Pyright, ESLint and Bandit run locally |
| Build | React production bundle and Docker images built; all eight long-running Compose services healthy |
| Dependency audit | pip-audit and full pnpm audit reported no known vulnerabilities after cryptography update |
| Backup | Encrypted archive restored into disposable PostgreSQL; schema/PAPER state and row counts checked |

The CI workflow is supplied but has not run on GitHub because this workspace has no connected Git repository. Local checks are not a claim of a green remote CI run. Browser-test screenshots are generated under `apps/web/test-results/` after enrollment material has left the page; traces are disabled to avoid capturing credentials.

Third-party deprecation warnings remain in Testcontainers and Starlette's httpx test-client integration. They do not skip tests or alter the asserted results. RiskEngine, order idempotency, ledger and exchange-recovery tests belong to later phases; the foundation's PAPER-only control properties do not establish trading safety.

Container scan results are recorded separately in [security verification](security.md).

2026-09-12 UI follow-up: enrollment now shows a locally generated QR with expandable manual key. Setup requires matching password confirmation, validated by React Hook Form/Zod; confirmation is never sent to the API. Spanish/English translations use i18next/react-i18next with a persistent language selector and localized dates and API errors. The Chromium workflow passed with mismatch rejection (zero setup requests), matching confirmation, QR/manual enrollment, language switching without losing form values, language persistence after reload and translated dashboard navigation. Lint, production build and pnpm audit passed. Mobile layout was visually inspected. Stored audit event codes/messages remain unchanged.

2026-09-12 Phase 2/3 follow-up: `pytest tests/unit tests/integration tests/property tests/contract -q` reports 168 passed (135 unit, 17 integration, 4 property, 12 contract; up from the 23 recorded above), 0 failed, 0 skipped. New coverage since the entry above: Phase 2 (market domain values, `FakeExchange` and a real `KrakenExchange` sharing one contract-test suite replayed against recorded API responses, instrument universe filters, a stateful candle-series data-quality gate, a Redis-backed hot-tier cache with real Testcontainers Redis, a checksummed atomic Parquet writer, a dependency-free feature engine, and the market scanner) and Phase 3 (deterministic regime classification, a `Strategy` port with a trend-following implementation, a confidence-weighted `SignalAggregator`, a `PortfolioAllocator` implementing RISK.md's Initial Policy table exactly, and a `RiskEngine` implementing RISK.md's Approval contract). `ruff check` and `pyright` (standard mode) pass with zero findings on every new file; `pip-audit` was run immediately after adding the one new dependency this added (`pyarrow`) and again after pinning past a CVE found in the first resolved version. One Hypothesis property test (`tests/property/test_risk_invariants.py`) exercises `RiskEngine`'s core approval-shape invariant across generated losses, drawdown, bucket exposure, proposed notional and spread â€” short of TESTING.md's full â‰¥95%-branch-coverage target for risk code, which remains future work alongside the rest of Phase 4. RiskEngine's own scope is intentionally partial: volatility/correlation limits and any AI-related check are not implemented (no volatility feature or AI provider exists yet), and reconciliation/breaker *state* is received as an input rather than computed (that mechanism is Phase 4 infrastructure). See `docs/PHASE_2.md` and `docs/PHASE_3.md` for the full per-slice acceptance evidence.
## Workspace layout refresh — 2026-10-14

Frontend intercepted suite: 20 passed (46.1s). Final mobile menu/checkbox CSS adjustment:
2 affected tests passed (26.0s), covering all 11 workspace routes at 1440, 1024 and 390px,
mobile navigation and light/dark screenshots. TypeScript and scoped ESLint clean.
Production web image built and deployed; 8 Compose services healthy, readiness HTTP 200.
Playwright MCP inspected deployed styles with synthetic intercepted API data, no real login:
375px document width, system font, 18px menu icon and checkbox. No funded-trading acceptance.
## Settings switches and analyst status — 2026-10-14

21 intercepted browser tests passed (41.4s), including native switch keyboard interactions,
44x28 tracks on desktop/mobile, drafts preserved on status refresh, explicit-only preference
saves, stale availability and all eleven route layouts. TypeScript and scoped ESLint clean.
Production web built/deployed; eight services healthy and readiness 200. Authenticated in-app
browser verified four switches and the original strict consensus unchanged. Explicit local
CLI probe returned Codex READY / Claude UNAVAILABLE; missing native worker started and status
timestamps refreshed. Operator had activated LIVE/READY; zero orders/fills at verification.
