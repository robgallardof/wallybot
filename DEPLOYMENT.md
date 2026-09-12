# Deployment and operations design

Status: the Phase 1 Compose stack, images, local scripts, health checks and encrypted foundation backup/restore verifier are implemented. Follow the [README](README.md) for current commands. Historical storage, external providers, monitoring profile, continuous WAL archiving and LIVE recovery remain planned.

## Production network

Fedora host with Docker Engine/Compose, approximately 16 GB RAM, synchronized UTC clock, durable disk and Cloudflare Tunnel/Zero Trust. Publish exactly `0.0.0.0:3333` on the gateway per the requested production contract. Route the public HTTPS domain through Cloudflare to `localhost:3333` when cloudflared runs on the host. If cloudflared runs in a container, `localhost` refers to that container: attach it to the edge network and use `gateway:3333` instead.

Binding all interfaces creates an origin-bypass risk. Restrict inbound reachability to the intended proxy path with Docker-aware packet filtering and verify from a separate host; do not assume the host firewall automatically protects published ports. A tunnel-only loopback binding is a possible later operator-selected hardening override, not the baseline requested here. Docker documents published-port binding behavior in its [service reference](https://docs.docker.com/reference/compose-file/services/).

Gateway routes web pages and assets to `web:8080`, `/api` and `/health` to `api:8000`; preserve the documented API prefix consistently. Cache hashed assets, never authentication responses. Public health exposes minimal status; diagnostic dependency details require login. Proxy supports authenticated event streaming with bounded connections and appropriate timeouts. TLS terminates at the configured Cloudflare/proxy boundary; trust forwarding headers only from that boundary.

| Network | Members | Purpose |
| --- | --- | --- |
| Edge | Gateway, web, API, optional cloudflared | Single entry; only gateway publishes a port |
| Operational (internal) | API, worker, scheduler, PostgreSQL, Redis | Private application state |
| Research (internal) | Research, PostgreSQL | Restricted analytics views and experiment metadata grants |
| Egress | Worker, configured AI/API component, optionally research | Required external provider access without publishing listeners |
| Monitoring (internal, optional) | Prometheus, Grafana and scrape targets | Internal telemetry, no public DB/metrics ports |

Segment credentials as well as networks. Research cannot access trading APIs or Redis queues. An egress-enabled bridge is not a destination allowlist; enforce tighter provider access with host/proxy controls when required. Compose `internal: true` isolates a network externally; services needing providers must have a deliberate egress path. See [Docker network reference](https://docs.docker.com/reference/compose-file/networks/).

## Processes and resource budget

Initial limits are engineering starting points to load-test, not measured capacity. Keep total bounded workload below host RAM and reserve approximately 3 GB for Fedora, Docker, filesystem cache and headroom.

| Container | Memory cap | CPU guidance |
| --- | --- | --- |
| wallybot-gateway | 128 MiB | Light proxy workload |
| wallybot-web | 128 MiB | Static assets |
| wallybot-api | 1 GiB | Bounded concurrency |
| wallybot-worker | 2 GiB | Higher relative CPU shares than research |
| wallybot-scheduler | 256 MiB | One scheduling leader via durable claims |
| wallybot-research | 4 GiB | One job, one CPU initially, low relative shares |
| wallybot-postgres | 2 GiB | Tune buffers/connections below container cap |
| wallybot-redis | 512 MiB | Set maxmemory below cap; explicit cache eviction policy |
| Optional monitoring combined | 1 GiB | Limit retention and cardinality |

Research cannot spawn unbounded child processes; configure BLAS/OpenMP thread limits, wall-clock deadlines and dataset quotas. CPU shares alone do not guarantee latency; set a research CPU cap based on actual host core count and load-test concurrent trading/research. Pause research on trading latency or memory pressure. Restrict DuckDB memory and temp-disk use. Do not mount Docker socket to launch backtests; isolation comes from the preconfigured research service.

## Startup contracts for Phase 1

Production target after cloning and preparing `.env` plus restricted secret files:

```sh
docker compose up -d
```

Compose includes database/cache health checks and a one-shot migration service. API/worker/scheduler wait for migration success and retry transient dependencies with bounded jitter. Never run migrations independently in every API replica. `/health/live` proves process responsiveness; `/health/ready` proves required dependencies/schema. Trading readiness additionally needs fresh data, reconciliation and account lease; an unavailable optional AI provider is distinct from a dead API. Store timestamped process heartbeats, and report their age.

All initial application services start in PAPER; research may idle without a job. Optional `monitoring` profile starts Prometheus/Grafana. Access monitoring through an authenticated admin gateway route or local operator tunnel, without public listener ports. Images use multi-stage builds, non-root users, pinned versions and health checks. Named volumes store PostgreSQL and durable application datasets; application containers are disposable.

## Local development

Full Docker uses the production topology with local secrets and `http://localhost:3333`. An explicitly named local-only cookie setting permits HTTP on loopback. Synthetic data is opt-in and visibly labeled; Phase 1 shows empty financial data because the simulator arrives later.

Hybrid development needs a deliberate exception: host processes cannot reach unpublished database ports through Compose service names. Supply `docker-compose.dev.yml` publishing only `127.0.0.1:5432:5432` and `127.0.0.1:6379:6379`. Invoke it explicitly:

```sh
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
```

Planned `make dev` / `scripts/dev.sh` / `scripts/dev.ps1` starts infrastructure with this override, then API on loopback 8000, worker, scheduler and Vite on loopback 3333. Vite proxies `/api` and `/health` to the API. It must not also start the Docker gateway on 3333. `uv` runs Python processes; `pnpm` runs the web app. Scripts terminate their child processes cleanly on exit. Do not auto-load the dev override in production.

This improves the original bare `docker compose up postgres redis` hybrid example: its private ports are unreachable from host processes without an override. Production still publishes only 3333. See [ADR-009](docs/adr/009-port-3333-gateway.md).

## Upgrade, backup and restore

Before upgrade: pause new risk, reconcile outstanding orders, record release/configuration versions and create a verified backup. Build/test images before changing production. Apply migrations once; start compatible services, check health/reconciliation, then operator rearm. Roll back an application image only if schema-compatible; otherwise roll forward or restore under an explicit recovery plan. Never run `down -v` as an upgrade step.

Proposed initial objectives requiring operator validation: database RPO 15 minutes and RTO 4 hours. Meeting the RPO requires continuous WAL archiving plus base backups; a daily dump alone does not meet it. Until implemented and tested, no RPO/RTO guarantee exists. Keep encrypted off-host backups of DB, configuration, strategy/research metadata and irreplaceable datasets; retain encryption keys separately under restricted access. Proposed retention is 7 daily and 4 weekly copies, adjusted to storage and retention requirements. Alert on backup age, archive failure and checksum failure.

Restore rehearsal uses isolated credentials/network with exchange egress disabled: restore base backup/WAL or selected logical dump, apply compatible app version, check schema, row counts, ledger balances, dataset hashes and authentication recovery. Record recovery point and elapsed time. Before any restored production instance can trade, reconcile the missing interval against the exchange; backup restore can resurrect old pending intents, so never submit them blindly. Rearm only after operator review. Schedule periodic restore validation when the automation exists; this document creates no scheduled task.

## Runbook requirements

On stale data or exchange disconnect: freeze new risk, recover stream snapshot/sequence, reconcile, then evaluate rearm. On DB failure: stop new submissions, retain uncertainty about in-flight requests and reconcile when DB returns. On Redis failure: recover caches and DB-backed work; do not erase durable control state. On disk pressure: stop research and ingestion expansion, preserve ledger capacity, alert; never delete financial/audit history automatically.

Emergency stop is not liquidation. Report cancellation/close requests and confirmed results separately. Track CPU/RAM/disk, service heartbeats, queue age, clock offset, feed/reconciliation age, unknown orders and backup status. Alert severity and deduplication prevent notification floods. Configure Fedora volume labeling narrowly where bind mounts need SELinux access; do not disable SELinux globally.
