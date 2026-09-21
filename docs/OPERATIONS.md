# Operations guide: health, pause/resume, breakers, redeploy, and the backup gap

Status: this is a day-to-day operator guide for the system as it actually runs today (PAPER only,
single admin account, Docker Compose on one host). It does not restate
[DEPLOYMENT.md](../DEPLOYMENT.md)'s design (network topology, resource budgets, upgrade/backup
targets) — read that for the full picture. This page exists to answer "what do I actually run"
during normal operation and incident response, and to state clearly where real disaster recovery
does not exist yet.

## Checking system health

**`GET /health/live`** (unauthenticated) — process responsiveness only: `{"status": "alive"}`. Does
not check the database, Redis, or anything else.

**`GET /health/ready`** (unauthenticated) — checks the Alembic schema revision matches what the API
expects, that the `control` row exists, and that Redis responds to `PING`, all within a 5-second
timeout. Returns `{"status": "ready"}` or a `503` with `{"status": "not_ready"}`. This is the check
to poll after a redeploy or migration.

**`GET /api/system`** (any signed-in role, `apps/api/system_routes.py`) — the authenticated detail
view: `api`/`database` status, Redis status (a live `PING`), per-service heartbeat age/status for
`worker`/`scheduler`/`research` (from `service_heartbeats`; a service that has never reported is
`UNAVAILABLE`, one silent for ≥30s is `STALE`), `exchange: "NOT_CONFIGURED"` (there is no LIVE
exchange — see [TRADING.md](TRADING.md)), `ai: "DISABLED"` (hardcoded — see [AI.md](AI.md); there
is no AI provider to report on), Telegram status (`ENABLED` only if a bot token and chat ID are
both configured), and `live_available: false` (also hardcoded — LIVE does not exist).

**`GET /api/dashboard`** — currently always returns `trading_available: false`, `equity: null`, and
an empty `positions` list. This is a known, intentional limitation stated in its own route: the
dashboard does not yet read from the real equity/portfolio state the decision loop and equity
tracker actually compute (see [TRADING.md](TRADING.md)); `GET /api/portfolio` is the route that
shows real PAPER ledger state today.

**`GET /api/events`** — the 100 most recent audit/system events (pauses, resumes, breaker clears,
etc.), for a quick recent-activity check without a database client.

## Pausing and resuming

**`POST /api/control`** (Admin, `apps/api/system_routes.py`) changes `status`
(`RUNNING`/`PAUSED`/...) and/or `environment`. It goes through `Control.change()`, which enforces
role/transition validity; a real state change is audited (`BOT_PAUSED`/`BOT_RESUMED`) and triggers a
Telegram notification if configured (WARNING severity on pause, INFO on resume). Pausing blocks new
entries; it does not cancel open orders or close positions — see [RISK.md](../RISK.md)'s breaker
action table for the distinction between pause, cancel, close, and emergency stop, none of which
this route alone performs beyond the pause/resume/environment toggle itself.

Telegram `/pause` and `/resume` commands exist too, but never flip control state directly — they
create a `TelegramConfirmation` that still requires the operator to confirm through
`POST /api/telegram/confirmations/{id}/confirm` (Admin + fresh MFA), the same authenticated path as
the web UI. See [SECURITY.md](../SECURITY.md) for the MFA-freshness requirement behind every
sensitive route referenced on this page.

## Circuit breakers

**`GET /api/risk/breakers`** (any signed-in role) lists all four breaker types
(`DAILY_LOSS`/`WEEKLY_LOSS`/`DRAWDOWN`/`RECONCILIATION`) and whether each is currently active, with
its reason and trip time.

**`POST /api/risk/breakers/{type}/clear`** (Admin + fresh MFA) clears an active breaker. It fails
with `404` for an unknown breaker type and `409` if the breaker isn't currently active. A successful
clear is audited as `BREAKER_CLEARED` with the clearing operator's ID.

A tripped breaker **stays tripped across restarts and across day boundaries** — nothing in this
codebase silently re-arms one (see [TRADING.md](TRADING.md)'s "Persistent circuit breakers"
section, and RISK.md's "a scheduler cannot silently reset a breaker at midnight"). If the decision
loop stops placing orders and `/api/risk/breakers` shows one active, that is very likely why; clear
it deliberately, only after confirming the underlying condition (loss/drawdown/reconciliation
health) has actually recovered — the route does not re-check that for you beyond requiring the
breaker to currently be active.

Only these four breaker types exist. RISK.md's fuller taxonomy (stale data, abnormal spread,
exchange outages, repeated execution errors, unknown orders, DB failure, clock drift) has no
trigger wiring — see [TRADING.md](TRADING.md) for what that means in practice.

## Redeploying

The pattern this repository's own session history (`.ai/CURRENT.md`) shows used repeatedly for
every code change, run from the repository root:

```sh
docker compose build
docker compose up -d
```

`docker compose up -d` brings up (or recreates, for images that changed) all core services:
`postgres`, `redis`, `migrate` (one-shot, applies pending Alembic migrations before dependents start
— never run migrations any other way), `api`, `worker`, `scheduler`, `research`, `web`, `gateway`.
After redeploying, confirm the migration actually landed and the stack is healthy:

```sh
curl -s http://localhost:3333/health/ready
```

expecting `{"status":"ready"}`. If it stays `{"status":"not_ready"}`, the schema revision the `api`
container expects doesn't match `alembic_version` in the database — the most common cause recorded
in this repository's own session history is rebuilding one image (e.g. `api`) but not its sibling
base image the `migrate`/`worker`/`scheduler` containers also depend on
(`docker-compose.yml`'s shared build anchor); rebuild every image with `docker compose build` (no
arguments) rather than a single service when in doubt.

An optional `monitoring` profile (`docker-compose.yml`) starts Prometheus + Grafana, separately from
the default stack: `docker compose --profile monitoring up -d`. Verified end-to-end (2026-09-21):
Prometheus scrapes `api:8000/api/metrics` directly over the internal `operational` network (that
route is intentionally unauthenticated — Prometheus can't hold a session cookie — and blocked at
the public edge by `docker/gateway.conf`'s `location = /api/metrics { return 404; }`); Grafana's
datasource and the one starter dashboard (`docker/grafana/dashboards/wallybot.json`) provisioned
cleanly with no errors in its own logs; all 5 alert rules in `docker/alerts.yml` were rehearsed with
`promtool test rules docker/alerts_test.yml` (synthetic time series, each alert confirmed to
transition pending→firing at the expected time) and cross-checked against the live Prometheus
instance's `/api/v1/rules` endpoint. Both services bind to `127.0.0.1` only (loopback) — neither has
built-in authentication strong enough to expose beyond the host; reach them via SSH port-forwarding
on a remote deployment. `wallybot/infrastructure/metrics.py` documents which of RISK.md's/
PENDING.md's "datos, colas, riesgo, UNKNOWN, conciliación, costes y recursos" metric categories are
covered (all except "costes" — no AI provider spend exists yet to measure) and which resource
metrics come for free from `prometheus_client`'s default collectors.

## Backups: there is none

**State this plainly, because it is a real, unclosed gap, not a documentation oversight:** this
repository has **no backup automation** — no scheduled dump, no WAL archiving, no off-host copy, no
tested restore procedure. `docs/PENDING.md`'s "Backups" transversal row is unchecked: "Copia fuera
del host, custodia separada de la clave, restauración periódica y cobertura de datasets
irreproducibles; definir RPO/RTO y verificar disco/retención" — none of this exists yet.
[DEPLOYMENT.md](../DEPLOYMENT.md)'s "Upgrade, backup and restore" section is explicit about the same
gap: "Proposed initial objectives requiring operator validation: database RPO 15 minutes and RTO 4
hours ... Until implemented and tested, no RPO/RTO guarantee exists."

There is no restore procedure to document here because none has been built or rehearsed. Do not
treat a manual `pg_dump` an operator might run ad hoc as equivalent to the tested, encrypted,
off-host, periodically-rehearsed backup/restore DEPLOYMENT.md describes as the target — none of
that exists today. If the `postgres` named volume is lost, so is every ledger, order, fill,
breaker, and equity-history row this system has ever recorded, with no recovery path.

This is worth treating as a priority alongside — arguably ahead of — further feature work: PAPER
already has real financial state (ledger, positions, equity history) that this gap leaves entirely
unprotected.
