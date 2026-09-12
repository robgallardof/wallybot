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
