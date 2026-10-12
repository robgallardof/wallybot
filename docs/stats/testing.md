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
