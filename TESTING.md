# Verification and acceptance plan

Status: executable foundation tests exist. See [recorded results](docs/stats/testing.md). Trading, exchange and quantitative scenarios below are required gates for later phases, not claims of present coverage.

## Test layers

| Layer | Tools | Required evidence |
| --- | --- | --- |
| Unit | pytest, pytest-asyncio, pytest-cov | Allocation, sizing, fees, PnL, indicators, scoring, regimes, signal aggregation, order transitions, AI schemas and settings |
| Property | Hypothesis | Risk/ledger/idempotency invariants across bounded valid and malformed inputs |
| Integration | Testcontainers, real PostgreSQL and Redis | Migrations, transactions, concurrency, outbox recovery, auth, jobs and paper pipeline |
| Contract | Shared pytest suites | Fake, Kraken and later adapters honor capability, precision, deduplication and lookup semantics |
| End-to-end | Playwright | Browser setup/login/MFA, dashboard, paper trade, decisions, pause/resume, configuration, logs/events |
| Failure | Controlled fault injection | Recovery after DB/Redis/network/process failures and ambiguous exchange results |
| Static/security | Ruff, Pyright, ESLint, Prettier, Bandit, pip-audit, frontend audit, Trivy | Typed boundaries, dependency/container findings and forbidden capabilities |

Phase 1 tests only implemented foundation behavior; later trade scenarios become required as their phases arrive. Never mark a skipped dependency-dependent suite as green acceptance. Use a Docker-capable CI runner for Testcontainers. Pin dependencies, record seeds and use injected clocks; do not depend on the wall clock or external exchange availability for mandatory tests.

## Safety scenarios

| Input / failure | Expected observation |
| --- | --- |
| Spec, asset, cluster or reserved exposure exhausted | Rejection or reduced size; no excessive reservation |
| Daily/weekly loss or drawdown at threshold | Latched breaker blocks increased exposure across restart |
| Stale, missing, NaN or corrupted data | No trade; specific quality/risk reason |
| Low liquidity, excessive spread or unhealthy exchange | No submission |
| Malformed AI output, prompt injection, timeout | Invalid recommendation cannot execute; configured HOLD/fallback only |
| Duplicate key, same payload | Original intent returned; one economic order |
| Duplicate key, changed payload | Conflict; no replacement order |
| Two concurrent approvals each fit alone | Aggregate reservation remains within capacity |
| Approval reused for changed intent or expired policy | Revalidation/rejection |
| Timeout after exchange accepts | UNKNOWN; lookup resolves original order; no blind retry |
| Crash before/after SUBMITTING or fill commit | Recovery reconciles; no duplicated fills/postings |
| Partial fill racing cancel acknowledgment | Fill ledger remains correct; remaining quantity reconciles |
| Redis restart / lost wakeup | DB scan recovers work; no financial truth lost |
| Postgres restart | New execution stops; resume only after durable recovery/reconciliation |
| Replayed TOTP / setup race / stolen CSRF request | Rejected, with security audit |
| Research credential tries production write | Denied by grants and use-case authorization |

Property tests generate sequences of fills, cancel races, approvals and restarts. Assert quantity is positive and quantized; rejected approvals produce zero submissions; sums of postings balance per currency; fills are applied once; no withdrawal operation can be generated; paper cannot reach live adapters. Exposure invariants apply at approval using current valuation and reservations; separate tests handle market-drift breaches with freeze/reduction policy. Test every listed risk rejection independently plus interactions; target at least 95% branch coverage for risk/accounting with explicit review of uncovered critical branches. Coverage alone cannot establish correctness.

## Simulator and reproducibility

Use a seeded FakeExchange implementing the same port as production: balances, minimums, market/limit capabilities, spread, fees, slippage, latency, partial fills, rejection, disconnect and accept-then-timeout behavior. Inject a clock and scripted outcomes. Disable network access in deterministic tests. No suite requires funded accounts or LIVE keys.

Replay uses the same strategy, risk and execution pipeline with a simulated clock and isolated paper ledger. Backtests enforce candle-close availability, train/validation/test splits and immutable dataset hashes. Test fee/slippage accounting against hand-calculated examples, including non-quote fees and cash flows. Validate statistical outputs on known datasets; disclose selection bias and correlated samples.

## Planned commands and CI

`make test` runs the documented required local suites; `make test-unit`, `make test-risk`, `make test-integration` and `make test-e2e` provide focused entry points. Integration owns Testcontainers startup/teardown; e2e owns an isolated test stack and seeded setup credentials. Provide PowerShell equivalents for Windows without Make. Never reuse development or production volumes for tests.

CI gates: lockfile install → lint/type-check → unit/property → real-service integration → frontend build/browser tests → Docker build → security scans. Save coverage, test reports and browser failure traces without credentials. Block deployment on failure; security exceptions require an owner, rationale and expiry. Evaluate Renovate/Dependabot in Phase 1; do not automatically promote dependency changes to LIVE.

## Phase 1 acceptance checklist

- Fresh Docker install starts through the documented one-command path after secret/bootstrap preparation; only gateway host port 3333 is published.
- `/setup` requires bootstrap possession, completes password and TOTP enrollment atomically and disables afterward.
- Login, MFA, logout, revoked sessions and ADMIN/VIEWER restrictions work through the browser.
- Dashboard reports PAPER, real dependency/heartbeat status and empty financial state accurately.
- PostgreSQL migration and persistence survive stack restart; Redis reconnects safely.
- Health endpoints distinguish liveness, readiness and private details; logs redact secrets.
- API, worker and scheduler recover from dependencies starting late; research is resource-limited.
- Unit, property where applicable, integration, browser, lint, types, image build and security gates pass on CI.

Track evidence and actual counts in `docs/stats/testing.md` when tests exist; never invent counts. LIVE has the additional [risk evidence gate](RISK.md).


## Frontend-only observability checks

From `apps/web`, run `pnpm exec playwright test --config playwright.ui.config.ts` to exercise observability screens with intercepted synthetic API responses. This mode starts only Next.js on port 3334 and requires no Docker, database or credentials. It is limited to `observability.spec.ts`; it does not replace the default authenticated integration or production CSP suites.
