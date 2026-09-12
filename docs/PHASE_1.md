# Phase 1 implementation backlog

Status: the executable foundation is implemented and verified locally. The checklist below records the original slices; [test evidence](stats/testing.md) distinguishes completed checks from unverified deployment conditions.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | Python/React workspace, locked dependencies, settings, quality tools | Reproducible installs, type/lint checks, no committed secrets |
| 2 | PostgreSQL/Redis, SQLAlchemy unit of work, Alembic, durable events/jobs | Empty DB migration and rollback/recovery integration tests |
| 3 | API health, structured logging, worker/scheduler heartbeats | Real dependencies visible; outages distinguish readiness from liveness |
| 4 | Bootstrap token, Argon2id, TOTP, sessions, ADMIN/VIEWER, CSRF | Setup race, MFA replay, session revocation, RBAC and rate-limit tests |
| 5 | React setup/login/dashboard/system shell | Browser workflow, PAPER label, genuine dependency state, accessible forms |
| 6 | Hardened Docker images, gateway 3333, resource limits, hybrid scripts | Fresh install and restart, only intended bindings, process cleanup |
| 7 | CI, security scans, backup/restore scripts and operating docs | Green automated gates and isolated restore rehearsal |

Slices may overlap only where dependencies permit. Authentication must protect diagnostic and control APIs before those endpoints become accessible. No exchange submission or LIVE control is included in Phase 1. Test fixtures may use synthetic data; user-facing financial simulation waits for the proper paper pipeline.

Delivered: locked Python/React workspace; isolated Docker services; PostgreSQL migration and roles; Redis throttling; password/TOTP bootstrap and login; recovery codes; session revocation; CSRF/origin enforcement; ADMIN/VIEWER access; PAPER pause/resume; dashboard/system/activity pages; maintenance job deduplication; structured logs; metrics endpoint; backup/restore verifier; CI workflow and dependency updates.

Remaining production validation: run the committed CI in a connected repository, configure and verify the actual Fedora/Cloudflare origin, test production HTTPS/cookie behavior, benchmark authentication/resource limits on the target host, and establish off-host backup custody. No remote deployment has been performed.

Not included in this release: monitoring Compose profile/Grafana/OpenTelemetry export, password or MFA replacement, user-management UI, log-search UI, stream delivery/outbox consumers, continuous WAL archiving, financial ledger, simulation, data providers, strategies or LIVE. These remain explicitly unavailable; the next product slice is Phase 2 market data. The research process currently reports its heartbeat only and has no agent endpoint or execution tools.

Later documentation (TRADING, STRATEGIES, AI, RESEARCH and BACKTESTING) should expand alongside implemented capabilities. Current core documents retain the full future design; their status paragraphs identify what exists today.
