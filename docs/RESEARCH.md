# Research jobs

Status: a real, working, narrow capability exists — re-running an existing backtest
(`ExperimentRecord`, identified by `experiment_id`) in an isolated process, entirely from local
Parquet data, with no network access and a queue/quota/cancellation/UI wired end to end. This is
**not** the "agentes de investigación aislados" (isolated research agents running arbitrary
tests/analysis/candidates/reports) `docs/PENDING.md`'s Fase 7 title describes — that depends on
Fase 6 (AI) existing first, which it does not (see [AI.md](AI.md)). What is built is real, tested,
and reachable through the UI today; this document describes exactly that, and no more.

## What a research job actually does

`run_pending_research_job` (`wallybot/application/research_runner.py`) claims at most one pending
`RESEARCH` job, looks up its `experiment_id` in `ExperimentRepository`, reconstructs the exact
`BacktestRequest` and `Instrument` the original run used (never re-resolving them live — the
research worker has no internet egress), and re-runs it through the same
`BacktestOrchestrator`/`BacktestEngine` path a fresh backtest uses (see
[BACKTESTING.md](BACKTESTING.md)). The result is persisted as a **new** `ExperimentRecord`, and the
job is marked `COMPLETED` with that new record's ID as its artifact. Any failure along the way —
missing experiment, insufficient historical data, an unexpected error — marks the job `FAILED` with
the exception message as the reason, never left `RUNNING` forever and never silently dropped.

This is deliberately the only kind of research job possible today: `apps/research_worker` has no
internet egress (`docker-compose.yml`'s `research` network is `internal: true`, per
`docs/PENDING.md`'s Fase 7 network-isolation requirement), so a research job can only re-run
something already backed by data on disk — never fetch new market data, never call a live exchange
adapter, never call an AI provider (there is none to call — see [AI.md](AI.md)).

## Queue, quota and cancellation

`ResearchJobRepository` (`wallybot/infrastructure/research_job_repository.py`) is a real PostgreSQL
queue: `claim_next` uses `SELECT ... FOR UPDATE SKIP LOCKED` so only one worker instance ever claims
a given pending job, ordered by `scheduled_at`. `request_cancellation` marks a job cancelled
immediately if it is still `PENDING`, or sets `cancel_requested` for a `RUNNING` job so
`research_runner.py` can honor it — a job in a terminal state (`COMPLETED`/`FAILED`/`CANCELLED`)
cannot be cancelled again.

`POST /api/research/jobs` (`apps/api/research_routes.py`, Admin-only) enforces
`MAX_ACTIVE_RESEARCH_JOBS = 5`: if `ResearchJobRepository.count_active()` (PENDING + RUNNING) is
already at 5, the request is rejected with `429`. This is a **system-wide queue-depth quota, not a
per-user quota** — the route's own comment is explicit: "this system has one admin account, not
per-user tenancy, so the queue depth is the only quota that makes sense here." It bounds runaway
enqueueing; it is not a claim about how much load `research_worker` can handle concurrently (it
claims and runs exactly one job at a time).

`GET /api/research/jobs` (any signed-in role) lists the 100 most recent jobs, and `DELETE
/api/research/jobs/{id}` (Admin-only) requests cancellation. Both routes keep the
`RESEARCH_JOBS_ACTIVE` Prometheus gauge in sync with `count_active()`.

## UI

`ResearchJobsPanel.tsx` (`apps/web/src/components/dashboard/`), composed into the Investigación
page, gives an ADMIN a form (experiment ID + purpose) to submit a job and a table of recent jobs
(status, attempts, artifact-or-error, requested-at) with a Cancel button on active rows. A VIEWER
sees the same table read-only, with no form. Before this session's work, the API was fully wired
and usable via `curl`, but nothing in `apps/web` ever called it — this UI is what closes that gap.

## What is not built

- **A generic experiment/test/analysis/candidate/report executor.** `docs/PENDING.md` Fase 7's own
  updated note states this precisely: research is "still only re-execution of an existing backtest
  by `experiment_id`, not a generic executor of 'tests, analysis, candidates and reports'" — that
  depends on Fase 6 (AI) existing first, "to have something to execute." There is no code path
  today where a research job does anything other than re-run a backtest.
- **Sanitized analytical read views separate from production data.** `docs/PENDING.md` Fase 7's
  "Proporcionar vistas/exportaciones saneadas y lectura analítica limitada; separar claves,
  escritura y red de producción" bullet is unchecked — `research_runner.py` reads Parquet + the
  `experiment_records` table directly, not through a separate sanitized view.
- **Agent-tool integration.** No typed, read-only AI tool surface exists for research to call
  (there is no AI provider to give tools to — see [AI.md](AI.md)). `docs/PENDING.md`'s "Integrar
  agentes con herramientas autorizadas para pruebas, análisis, candidatos y reportes; código
  generado requiere revisión" is unstarted.
- **Service identity and replay protection for an agent HTTP endpoint.** No such endpoint exists;
  SECURITY.md's "Do not create an agent HTTP endpoint until needed" applies — none has been needed
  yet.
- **A human-reviewed promotion workflow.** Nothing in this codebase promotes a research artifact
  into anything else; there is no self-approval risk here because there is no approval path at all
  yet.

## Isolation this capability already respects

Research credentials are scoped separately (`wally_research` DB role) per SECURITY.md's "Secret and
agent isolation" section, and the research process has no trading credentials, no execution
capability, and no network egress. A research job cannot place an order, change risk limits, or
reach a live exchange — it can only read Parquet/Postgres and write a new `ExperimentRecord` and its
own job status. See [SECURITY.md](../SECURITY.md) for the full isolation model this relies on, and
[BACKTESTING.md](BACKTESTING.md) for what the underlying re-run actually computes.
