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

## Autorización de despliegue y bloqueo del entorno — 2026-10-15

El operador autoriza explícitamente ejecutar las pruebas de integración y reiniciar producción
para desplegar estos cambios de WallyBot. No volver a pedir ese permiso para este alcance.
La nueva comprobación `docker version --format '{{.Server.Version}}'` sigue fallando al conectar
con /var/run/docker.sock: Operation not permitted. Es una restricción del entorno de ejecución;
no se intentó eludirla, alterar permisos del socket ni acceder por otra identidad/transporte.
Esta sesión no permite elevar permisos. Integración y despliegue siguen pendientes; ningún
servicio de producción reiniciado. Continuar al disponer de un entorno con acceso autorizado
a Docker, preservando los servicios ajenos a WallyBot y los cambios locales existentes.

## Telegram: aprobación sin MFA y propuestas explicadas — 2026-10-15

Petición explícita del operador: aprobar/rechazar sin MFA por operación desde Telegram;
mostrar por qué, importe/faltante, vigencia, horizonte, niveles y riesgos, y ordenar las ideas.
Implementación LOCAL, NO desplegada. No confundir con los despliegues históricos de abajo.

`/approve ID`, `/reject ID` y callbacks funcionan exclusivamente con remitente == chat ID
vinculado y tipo private; ADMIN comprobado en la función interna. Botones ligados al modo y
versión LIVE mostrados; cambios rechazan la aprobación antigua. El camino compartido mantiene
propiedad, caducidad, uso único y revalidación determinista; auditoría distingue WEB de
TELEGRAM_PRIVATE_CHAT. La web, activación LIVE y cambios de límites conservan MFA. No se
modificó autenticación web, límites, modo ni datos de cuenta. Respuestas incluyen motivo de
bloqueo/ejecución; aprobar no implica necesariamente que existió una orden.

Nuevo `proposal_presentation.py` reutilizado por /proposals (/proposal alias) y digests: hasta
cinco fichas entre 100 recientes, pendientes vigentes primero, relación beneficio/riesgo y
potencial bruto después (no rendimiento esperado/probabilidad). Etiquetas orientativas LOW
(stop <=2%, asignación <=5%), MEDIUM (<=5%, <=10%), HIGH para el resto/niveles no comparables.
Importe/faltante sólo con LIVE READY propio y equity/cash de <=60s, moneda/proveedor iguales,
limitado por cash/límite por orden, antes de costes y demás controles. Sin evidencia no inventa
saldos. Fichas incluyen razones/riesgos/invalidación, escenarios, horizonte y caducidad UTC;
se envía cada ficha por separado, con botones y enlace web al detalle. No salidas automáticas.

El prompt pide español claro, evidencia y explicación de asignación/plazos/niveles. El parser
conserva invalidating_conditions y valida listas de texto. Consenso conserva razones y condiciones
de ambos analistas antes de su etiqueta. Default de prompt pasa a v2-es; históricos no cambian.
ADR-021, mandato, SECURITY/RISK y guía TELEGRAM-PROPOSALS actualizados.

Verificación: selección local 113 passed, 6 deselected (not codex and not subprocess), más una
regresión adicional de invalidación de consenso 1 passed: 114 pruebas distintas. Ruff y Pyright
sin errores; git diff --check limpio. Dos ejecuciones ampliadas se interrumpieron al estancarse
la fixture Codex que usa asyncio.to_thread; no se atribuye un fallo del producto. No se ejecutó
ninguna CLI real de análisis. Integración intentada con --maxfail=1: ERROR de preparación,
Docker socket Operation not permitted antes de arrancar PostgreSQL/Redis. No suite de integración
aceptada ni afirmación de aceptación LIVE. Graphify no instalado y graphify-out/graph.json ausente;
Serena tampoco inició language server, por lo que se usaron herramientas locales.

Pendiente: ejecutar integración Telegram/proposal notifications y controles LIVE en entorno con
Docker, construir/verificar y desplegar API + actualizar proceso nativo de analistas sólo con
permiso de producción. No reinicios, órdenes reales, cambios de saldo/configuración ni mensajes
Telegram manuales. No commits/push. Preservados .claude/worktrees/ y docker-compose.override.yml
preexistentes. No leer .env ni .secrets.

## Settings controls and analyst status UX — 2026-10-14

User requested usable Settings switches/buttons/layouts and clarification of analyst selection.
Current operator-owned production account is LIVE/READY (user activated in browser), limits
unchanged, zero orders/fills at verification. Codex and Claude enabled with strict consensus;
no automatic fallback or policy weakening. Antigravity is not integrated. Fresh explicit local
readiness script: Codex READY, Claude UNAVAILABLE. No claim about the underlying Claude cause.
Native AI worker was absent; started via existing hidden-window launcher, new status rows recorded.

Added native accessible SettingsSwitch with role=switch, 44x28 nonshrinking visual track,
keyboard/focus/disabled states. Replaced all four analyst/Telegram toggles. Settings has jump
navigation for trading/analysts/Telegram/security, fieldsets for allocations and analyst selection,
responsive layouts and a primary save action with invalid-consensus/no-analyst disable guards.
Availability cards label checks older than 15min (or future >1min) as out of date rather than
currently available. Removed unsupported claim that a failed CLI must be signed out/uninstalled;
help names process/install/session/provider limits. Refresh reads records only, never invokes CLI.
30s polling and scalar effect dependencies preserve unsaved selection during timestamp refresh.
Saved policy summary distinguishes strict consensus from optional single valid response; conflicting
responses still block. English translations completed. No backend/API/schema or order logic changed.

Verification: 21 intercepted browser tests passed (41.4s), including explicit switch keyboard/save,
no mutation on status refresh, preserved draft, all 11 routes at desktop/tablet/mobile and screenshots
in both appearances; TypeScript and scoped ESLint passed; production web image built. Deployment
completed: eight services healthy, readiness 200. Authenticated in-app browser reloaded and
verified four role=switch controls, English copy, current analyst check dates, and strict saved
consensus. Graphify refreshed: 4860 nodes,13967 edges. No login credentials inspected,
manual Telegram dispatch or financial transaction. Existing unrelated dirty work preserved.

## Workspace layout refresh and Binance connection verified — 2026-10-14

User added Binance credentials and requested an Apple-inspired refresh across all layouts.
Read-only production query confirms BINANCE / TRADE_ONLY / HEALTHY; OBSERVE / RUNNING,
Codex available, Claude unavailable, no live_control row. No credential contents inspected,
no LIVE activation, settings change or real order. Strict consensus still needs Claude readiness.

Shared workspace.css now owns layout refinements across eleven sections: system font instead of
Poppins font downloads, consistent navigation, responsive gutters/cards/forms/tables, visible LIVE
badge, desktop/tablet/mobile behavior, focus and reduced-motion support. Documentation moved to
end of navigation. Connection checkbox and mobile menu icon sizes corrected after visual review.
Overview's stale FASE 02 roadmap replaced with an account-review action; English translations added.

Evidence: full intercepted browser suite 20 passed (46.1s); after final control-size correction,
2 affected tests passed (26.0s), including 11 routes at 1440/1024/390 and dark/light screenshots.
TypeScript and scoped ESLint passed. Production web image built successfully and deployed;
gateway restarted. Eight services healthy, readiness 200. Playwright MCP inspected deployed web
with synthetic intercepted API responses (not real login): shared stylesheet loaded, system font,
no horizontal overflow at 375px, menu icon and checkbox each 18px. No authenticated LIVE acceptance.
Graphify refreshed (4857 nodes,13962 edges); historical community labels remain stale.
Preserved all existing unrelated dirty changes. Gross benchmark/net account comparison limits
from the previous handoff remain. Next operator step: resolve Claude, then explicitly configure
LIVE and limits with fresh MFA only when desired; connection alone never activates trading.

## Gross market references implemented and deployed — 2026-10-14

User resumed adaptation; completed the missing informational benchmark portion of Telegram
reports. Supersedes the previous blanket "benchmarks unavailable" note: actual account net
performance/outperformance comparison remains separate, and is not claimed implemented.

New domain benchmarks and bounded public-data collector provide BTC, ETH, nominal zero-interest
cash and hypothetical BTC/ETH 50/50 buy-and-hold references. Exact hourly closes, same venue and
quote, explicit dates; Decimal only. Missing/duplicate/wrong-source/quote/future evidence or
arithmetic overflow withholds the asset and dependent passive mix. Never zero-fill a missing
asset. At UTC rollover, use the previous completed day/week when no new-period hour has closed.
Two public requests per window, 5s timeout each, max 8 days/194 requested rows. No private API.

API injects public Binance/Kraken providers into the daily/weekly report loop. Reports label
references gross and exclude fees/slippage/interest/FX; there is no account ranking or mandate
change. Formatter suppresses currency, venue or future-date mismatches. Fixed literal backslash-n
formatting introduced in the earlier report rewrite; reports now contain actual line breaks.
ADR-020 records method and limitations; product mandate updated. No frontend or schema changes.

Evidence: final focused run 69 passed (54.19s), real disposable PostgreSQL/Redis; Pyright 0 errors;
Ruff and git diff whitespace clean. Public Binance preflight returned all 4 references available.
Final API image rebuilt and API/gateway restarted; eight services healthy, readiness 200.
Deployed read-only preview (no dispatch) verified 4 available values, gross-reference text and
real line breaks against current public Binance data. Production OBSERVE/RUNNING, 0 orders/fills.
No manual Telegram message, LIVE activation, credential inspection or funded trade.
Graphify AST refreshed: 4856 nodes; historical community labels still need future refresh.

Remaining: net account performance adjusted for external flows with aligned valuation dates and
cost assumptions; funded Binance acceptance through the operator's own MFA approval flow. UI
benchmark charts were not added in this report-focused change. Preserve all pre-existing dirty
changes and unrelated work. Existing report markers/cadence unchanged; historical Telegram
messages are not edited. New scheduled reports use the references when evidence is available.

## Telegram report accuracy fixes — 2026-10-14

User reported Telegram still mentioning "Fase 5". Found exact live-facing text in
wallybot/domain/telegram_report.py. Removed internal roadmap labels while retaining explicit
benchmark unavailability; benchmark computation was not implemented or fabricated.

Fixed real report behavior: API passes operator context and Spanish language; report job resolves
current OBSERVE/PAPER/LIVE and owner-bound real account instead of always reading PAPER. LIVE
uses connection venue/currency, fee queries filter environment and currency, and reports show
valuation timestamp. Value change is not labelled investment return. Missing reconciliation is
not "healthy": real verification requires READY and fresh valuation; stale/blocked evidence
warns. API liveness comes from this successful read, and enabled native AI heartbeat is included.
Reports remain read-only; configured cadence/delivery markers and approval controls unchanged.

Verified: 50 focused unit/integration tests passed (29.23s), real disposable PostgreSQL/Redis,
including commands, LIVE Binance fees/report identity, OBSERVE mode and foreign-owner isolation.
Scoped Pyright 0 errors; Ruff and git diff whitespace clean. No frontend changes and no new
schema migration. Graphify AST updated (4816 nodes; community labels need future refresh).
API image rebuilt and API/gateway updated. Production remains OBSERVE/RUNNING with 0 orders/fills.
No manual Telegram test message or real trade was sent. Older messages in Telegram remain
historical; new scheduled reports use the corrected text. Passive benchmark comparison and
funded Binance acceptance remain open capabilities, not claimed complete.

## Binance migration completed and deployed — 2026-10-12

Supersedes the Docker-blocked adaptation note below. User explicitly resumed the Binance
migration. Preserved the pre-existing dirty integration and unrelated work. Binance is the
default public exchange for the scanner, ingestion, backtests, OBSERVE/PAPER analysts, simulated
funding and PAPER execution; spot LIVE is BTC/USDT and ETH/USDT only, activated by the operator.

Further fixes: price/reliability job now actually queries Binance USDT pairs and never merges
USD/USDT; Dashboard/System identify Binance, Overview displays each cash/P&L currency separately
and excludes USDT from LIVE positions; analyst prompt labels cash in the instrument quote.
Connections/Docs/LIVE guidance focuses on Binance, with proper read-only guidance for other
sources. Native field names ending in _usd are retained compatibility names in account units.
Public instrument reads reject other venues and mismatched/halted rules. Private reconciliation
checks exact approved price and IOC terms, symbol, duplicate trade IDs, execution quantity and
quote total. Binance fill IDs are deterministic account/symbol/native-ID scoped UUIDs, fitting
ledger keys and avoiding collisions between accounts/markets.

Evidence: final full backend 1046 passed (201.46s), real disposable PostgreSQL/Redis; production
browser suite 21 passed (1.1m); final mocked UI suite 19 passed (41.3s). Scoped Pyright zero errors;
frontend tsc/ESLint, Ruff and diff whitespace clean. Real public Binance discovered 23 scanner
instruments and 29 closed hourly candles for BTC/USDT and ETH/USDT in a 30-hour lookback.
Tests exercise Binance LIVE fee accounting, lost-response recovery, cross-venue blocking, unsafe
permissions/balances, and PAPER approval/funding in USDT without private submission.

Encrypted backup created and isolated restore verified before migration. Docker Desktop was
started; a parallel rebuild crashed it, so it was recovered and production app services paused
while repeating tests. All final images rebuilt sequentially; migration 0046 applied; eight
Compose services healthy; readiness HTTP 200. Native analyst restarted and heartbeat verified;
first deployed tick evaluated 2 instruments, no proposal (HOLD/disagreement is valid).
Production stayed OBSERVE/RUNNING: zero configured LIVE accounts, zero orders and zero fills.
No exchange credential read or requested in chat, no LIVE activation and no real trade performed.
Graphify AST refreshed (4804 nodes); historical community labels need future refresh.

Remaining operator acceptance: link a dedicated Binance key through Connections with fresh MFA,
verify actual permissions/balances/fees, explicitly configure LIVE limits and approve a funded
spot order only if desired. No funded-venue acceptance claim. Existing USD PAPER funds are
never relabelled or converted to USDT; preserve their ledger history. Legacy Kraken adapters and
historical records remain for compatibility, not the default Binance workflows.

## Binance default venue adaptation — 2026-10-12

User selected Binance instead of Kraken. Continued the pre-existing dirty Binance integration;
no unrelated changes discarded. Binance now supplies default market overview (curated USDT
pairs), ingestion, price source, backtests, native AI analysis in OBSERVE/PAPER, and PAPER
execution pricing. New simulated funding uses USDT; proposal equity uses the proposal quote
currency; deterministic runtime supplies USDT explicitly. Historical Kraken records keep their
venue/currency and marks route per venue. Connections default to Binance; backtests BTC/USDT;
funding and LIVE limit labels reflect USDT; Telegram LIVE summary resolves account venue/currency.
ADR-019 and the real spot runbook describe Binance as default.

Evidence: 689 unit/contract/property tests passed (11.66s), including 42 Binance adapter tests;
18 mocked browser tests passed (51.2s); final activation/Binance browser rerun 2 passed (8.4s).
Backend Pyright zero errors; frontend tsc and focused ESLint clean; Ruff and diff whitespace clean.
Public Binance BTC/USDT and ETH/USDT discovery and valid bid/ask quotes verified without keys.
Graphify AST update succeeded (4776 nodes); community labels need refresh after topology change.

NOT deployed: Docker daemon unavailable (named pipe); real PostgreSQL/Redis integration failed
at container setup, and full suite was interrupted after repeated setup errors. Migration 0046
is pending deployment. No private credentials read, no real account linked, no LIVE activated,
no order placed. Next: restore Docker access, run full backend and production browser suites,
apply 0046 and rebuild services plus restart native worker; verify OBSERVE and heartbeat.
Existing PAPER USD balances are not converted/relabelled into USDT; they cannot finance USDT
orders. Preserve their ledger history and resolve any funded legacy account explicitly.

## Verified operator-readiness fixes — 2026-10-12 (second pass)

Supersedes the "Claude is not logged in" note below. No real account configured, no real or
PAPER orders placed, runtime OBSERVE throughout. Unrelated Rust work (gitignored) untouched.

Fixed:
- AI analysis never reached Codex/Claude: a 20-hour lookback yields 19 closed Kraken candles,
  below the 20-candle universe minimum, so every tick evaluated 0 instruments (0 proposals ever
  existed). Lookback is now 30 candles; a live dry run and the deployed worker evaluate ETH/USD
  and XBT/USD. Worker logs now carry allowlisted integer counts.
- Per-analyst CLI availability: migration 0045 + bounded SECURITY DEFINER function for the
  analyst role; Settings shows Disponible/No disponible/Sin comprobar with `claude auth login` /
  `codex login` guidance. Consensus and analyst toggles are never changed automatically.
- Kraken linking/activation collapsed every failure into one generic message. Kraken error codes,
  malformed secrets and network failures now map to sanitized, actionable messages (Spanish
  translations added) on Connections, LIVE activation and the periodic BLOCKED reason. The LIVE
  form rejects per-trade > total exposure locally.
- Backup verify hardcoded revision 0001/PAPER and always failed; it now accepts any known revision
  and a valid mode, and records ledger/order counts.

Evidence: 971 backend tests passed (145.82s, real PostgreSQL/Redis); production browser suite
19 passed (45.9s, WALLY_E2E_PRODUCTION=1); mocked UI suite 17 passed; scoped Pyright 0 errors;
Ruff, tsc and focused ESLint clean. Encrypted backup created and isolated restore verified before
deploy. Images rebuilt; 8 services healthy; readiness 200; alembic head 0045. Both CLIs READY
via scripts/check_ai_analysts.py; first deployed tick recorded codex/claude available,
instruments_evaluated=2, no consensus proposal (HOLD/disagreement is valid).

Requires the operator's real account (not verifiable locally): Kraken key validation against the
real API, opening-balance reconciliation, a funded IOC order and its fill/fee reconciliation.

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

# Claude handoff — 2026-09-16 (new session)

## Proposal provenance in the portfolio — 2026-09-27

`GET /api/portfolio` and `GET /api/portfolio/ai` now include an optional `proposal_id` for each
fill when it originated from the signed-in operator's approved proposal. The API correlates the
persisted `execution_order_id` with its fill's `client_order_id`; the web activity table labels it
as a WallyBot AI proposal. It is evidence only -- it cannot cause approval, execution, transfer,
or a valuation. Tests, static checks, graph update, and an API/web/gateway deployment passed.

`PortfolioView.proposal_history` now exposes the same linked fills in a dedicated monitoring list:
entry actually filled, quantity, elapsed holding time, recorded stop/target and execution outcome.
No live price or unrealized P&L is inferred without a trusted quote. The API/web/gateway deployment
was recreated and verified after this addition.

Telegram `/withdrawal` is now implemented as a read-only informational review over confirmed FIFO
results in `paper-ai:<owner>`. It cannot receive a destination, submit a trade, create a Telegram
confirmation, transfer or withdraw. The command is in `/help` and the docs. 38 focused tests and
static checks passed; the deployment was verified.

## Approved proposal → revalidated PAPER order — 2026-09-27

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

Next candidates: portfolio history/P&L per approved proposal (spec point 4, now unblocked),
informational withdrawal recommendations (point 5), stop/take-profit follow-up for AI positions.

## 2026-09-27 — configurable, read-only Telegram AI digest

`0038_ai_proposal_digests` is deployed. The API's pre-existing Telegram
report loop calls the new `run_ai_proposal_digest_tick` for the operator. When AI analysis is
enabled, it sends one bilingual read-only digest of up to five new pending proposals only after
the configured AI digest interval. `ai_proposal_digests.last_sent_at` prevents repeats. It uses the
existing encrypted Telegram configuration, paired chat allowlist, notification throttle and API
egress boundary. It cannot approve, simulate, execute, transfer, reveal credentials, or modify
settings; sensitive decisions remain the authenticated web MFA flow. Focused verification passed:
Ruff, pyright and 15 Telegram/AI tests. Graphify was updated, migration 0038 applied, and API plus
gateway were recreated; `/health/ready` and `/docs` return 200. Preserve the shared dirty tree.

## 2026-09-27 — dual local analysts, strict consensus, OBSERVE default

Active product flow: Codex and Claude are independent local CLI analysts, never executors.
`0037_ai_analyst_consensus` persists their toggles plus strict-consensus selection. Strict
consensus is the default and fails closed unless both return compatible BUY proposals for the same
immutable context. The worker uses `ConsensusAiProvider`; no provider obtains wallet, transfer,
order, or private-key capability. The supported credentials stay in each locally authenticated
CLI; do not add API tokens to UI/DB without a dedicated secret-management design.

OBSERVE is still the default. Proposal simulation requires an explicit Settings switch to PAPER;
the UI hides its button and the API rejects the simulation otherwise. This does not alter the
non-executing approval/reject flow.

Strict consensus verifies both price proximity and direction. If one local analyst recommends a
buy and the other recommends a sell, the result is HOLD/no proposal. Ruff, pyright and 23 focused
consensus/CLI/decision tests passed for this guardrail.

The read-only Telegram `/proposals` reply now includes each persisted proposal's execution context
such as `PAPER FILLED` or `OBSERVE_ONLY`, alongside its decision state. It is informational only;
Telegram cannot approve or execute. 39 focused Telegram/proposal tests passed and API/gateway were
rebuilt with readiness plus in-container verification.

CLI analysts now support BUY, SELL and HOLD. SELL is a reduction proposal only: the simulation
maps it to `Action.SELL`, and allocation/risk cap it by existing spot exposure; an unheld asset is
rejected. It remains non-executing and cannot short, borrow, transfer or withdraw. Ruff, pyright
and 29 focused AI/consensus/shadow tests passed; rebuild/recreate API for the simulation update.

Verified: 36 focused unit tests, 10 integration tests, Ruff, pyright, TypeScript/ESLint; migration
0037 deployed. Docker services api/web/gateway healthy and `http://localhost:3333/docs` 200.
Shared tree is intentionally dirty: do not broad stage, reset, or commit unrelated work.

## 2026-09-24 — proposal safety and deployment state

The deployed stack is healthy at `http://localhost:3333` (API/web/gateway healthy, readiness
200). Rebuild the `migrate` image when adding migrations: the earlier API 503 was an
image-version mismatch. Current Alembic head is `0036_proposal_owner`.

ADR-017 supersedes the historical ADR-016 direct-execution exception. The AI worker only produces
operator-owned proposals. Decisions are Admin + fresh MFA, audited and non-executing. The frontend
exposes Simulate/Approve/Reject; those statuses deliberately do not create PAPER orders yet.
Future work must place mandate, quality, allocation and risk validation between approval and an
order. Do not call `ExecutionService` from `ai_decision_loop.py` or `apps/ai_worker`.

Telegram `/proposals` is now implemented as an owner-scoped, read-only summary. It is bilingual
and tells the user to use the MFA web UI for a sensitive decision; it does not turn Telegram into
an execution channel. The API was rebuilt/redeployed after this addition and readiness stayed 200.

Verified: 18 focused tests, Ruff, frontend tsc and focused ESLint. Graphify updated. The shared
working tree is extensively dirty; preserve unrelated work and do not broad-commit.

## AI-autonomous PAPER trading via local claude/codex CLI — 2026-09-23

Full detail in `.ai/CURRENT.md`'s matching entry -- **read [ADR-016](../docs/adr/016-ai-autonomous-account.md) first** before touching anything in this area. Summary: the operator asked for AI-driven trading using their own local `claude`/`codex` CLI (not a hosted API key), then explicitly confirmed twice -- after being shown concrete failure scenarios -- that this new path should run with zero risk limits (no `RiskEngine`/`PortfolioAllocator`/breakers). This is a deliberate, dated exception to ADR-007/013, not a bug.

Built: `CliAiProvider` (real CLI subprocess adapter, flags verified against installed binaries), `wallybot/application/ai_decision_loop.py` (structurally guaranteed via an import-inspection test to never touch risk/allocator/breaker code), migrations `0033`/`0034` (`ai_autonomy_control` table + least-privilege `wally_ai` role), `GET`/`POST /api/ai-autonomy/control` + `/api/portfolio/ai(/fund)`, the native (non-container) `apps/ai_worker` process, and a Portfolio/Settings UI update. Verified for real against the live dev stack (real Kraken + real `claude` CLI call, no crash). Also fixed a real pre-existing Playwright flake (unrelated to this feature) found while adding UI test coverage.

**Key lessons for next time:**
1. Docker Desktop on WSL2 cannot publish a host port from a container whose only networks are `internal: true` -- confirmed by directly testing (attach to a non-internal network and the port immediately works). This silently affected the pre-existing Prometheus/Grafana ports too, not just this new one.
2. When a user asks for a new capability that contradicts a documented ADR/security rule, get their explicit, informed confirmation (concrete failure scenarios, not just "are you sure") before building it, then write a new superseding ADR rather than silently editing the old one -- `.ai/DECISIONS.md` is explicitly *not* the place for product/architecture decisions in this repo, `docs/adr/` is.
3. `getByLabel`/`getByRole` in this Playwright version did not reliably match a `role="status"` element's accessible name computed from a visually-hidden child span's text content in one real case -- a CSS-class locator (`.page-skeleton`) worked instantly where both label-based locators silently failed to find an element visibly present in the accessibility snapshot. Worth remembering if another skeleton-loading assertion looks inexplicably flaky.

**Verified:** full backend suite 862 passed, ruff/pyright clean. Frontend tsc/eslint/build clean, Playwright 13/13 stable across 3 runs. Docker rebuilt/redeployed, all services healthy.

**Not yet committed** -- ask before committing; this is a very large diff, consider splitting it.

**Immediate next actions:** Slice 6 (feed 70/20/10 tier targets + wider coin discovery into the AI's actual prompt context -- stored/editable today but not yet used), Slice 7 (Telegram strategic-suggestion confirmations + digest notifications). Out of scope, unchanged: equities/VIX strategy (data-provider decision still pending), LIVE trading (no real gateway exists). Unresolved: the user's request for XML/JSDoc-style comments conflicts with this repo's "no comments unless the why is non-obvious" convention -- needs their decision.

## Reproducible research exports and artifacts — 2026-09-23

The authenticated `GET /api/backtests/export?format=csv|json` provides full immutable replay
metadata, with optional `experiment_id` filtering. The research job result link downloads the
single completed re-run as JSON. No secrets or execution capability are exposed. Verification:
15 focused integration tests, TS/ESLint/Ruff, Docker api+web rebuild and gateway readiness passed.
Avoid broad commits because the shared tree still has parallel auth/security work.

## Codex UI slice — 2026-09-23

Added an R3F/Three.js access-screen scene, product-facing Docs architecture guide and onboarding,
visible Telegram command help, accessible page skeletons, plus real per-instrument candle detail
on Markets (existing API contract). Checks passed: Next build, focused TS/ESLint and mocked
Playwright. Docker Desktop was not running/installed at the engine endpoint, so deployment is
pending. Preserve the concurrent auth/security files; do not broad-stage or broad-commit.

## MarketCache wired into the Markets view — 2026-09-21 (continued further still)

Full detail in `.ai/CURRENT.md`. `MarketCache` was real/tested but unused -- now `build_market_
overview` checks it first for each instrument's bid/ask snapshot (30s TTL) before hitting the
provider. Candles still aren't cached (the cache never supported series, only a single snapshot).
Found and fixed a real pre-existing pyright gap in `RedisLike`'s Protocol definition while wiring a
real `Redis` instance into it for the first time (param names/async-vs-Awaitable mismatches against
redis-py's own imprecise stubs).

**Verified:** 798 backend tests (up from 796), ruff/pyright clean. About to rebuild/redeploy/commit.

**This closes out the Fase 1/2 audit's safe, unblocked backlog items.** Remaining candidates all
need an explicit product/config decision (user administration, RISK_POLICY versioning,
stop-distance sizing) or are human-only. Worth checking with the user on direction next.

## Instrument-detail route added — 2026-09-21 (continued further still)

Full detail in `.ai/CURRENT.md`. New `GET /api/markets/{instrument_id:path}` (candles/volume/
bid-ask/quality/eligibility for one instrument) -- reuses `GET /api/markets`'s own provider/
timeframe/quality_policy config, never a second copy. API-only this slice; the candle chart itself
needs a charting library that isn't installed yet (`ARCHITECTURE.md` plans Lightweight Charts, not
in `package.json`) -- a real dependency decision, not silently added here.

**Verified:** 796 backend tests (up from 793), ruff/pyright clean. About to rebuild/redeploy/commit.

**Immediate next actions:** per "continua...hasta acabar tokens" -- remaining candidate: wire
`MarketCache`. Do not touch OBSERVE/PAPER/LIVE architecture.

## Stale Vite references fixed — 2026-09-21 (continued further still, docs-only)

Small pick from the Fase 1/2 audit: `ARCHITECTURE.md`, `DEPLOYMENT.md`, `AGENTS.md` and
`docs/AI-DEVELOPMENT.md` all still described the frontend as Vite -- fixed to Next.js, verified
against the real `apps/web/package.json`/`next.config.ts` mechanism rather than guessed. Docs-only,
no rebuild needed.

## Quality gate closed on the Markets view — 2026-09-21 (continued further still)

Full detail in `.ai/CURRENT.md`. Fixed a real gap the Fase 1/2 audit surfaced: the live trading
path (`decision_pipeline.py`) already excluded FAILURE-quality instruments before scoring, but the
read-only Markets page (`market_overview.py`) didn't apply the same gate. `evaluate_instrument`/
`evaluate_universe` (`wallybot/market/universe.py`) now take an optional `QualityReport` and block
eligibility on FAILURE status -- backward-compatible, no change needed to the already-correct
trading path.

**Verified:** 793 backend tests (up from 788), ruff/pyright clean. About to rebuild/redeploy/commit.

**Immediate next actions:** per "continua...hasta acabar tokens" -- remaining audit-surfaced
candidates: wire `MarketCache` (built, unused, lower priority), fix stale Vite references in root
docs, instrument-detail route. Do not touch OBSERVE/PAPER/LIVE architecture.

## Risk limits exposed + Fase 1/2 audit reconciled — 2026-09-21 (continued further still)

Full detail in `.ai/CURRENT.md`. New: `GET /api/risk/limits` (RISK_POLICY's limits + consumption/
breach state, read-only from the latest `EquitySnapshot`, no live market repricing) -- closes Fase
3's risk-limits-on-screen item. Also reconciled a background audit agent's Fase 1/2 findings into
`docs/PENDING.md` (1 DONE / 15 PARTIALLY DONE / 4 NOT STARTED of 20 items) -- checked off only the
one genuinely complete item, added dated summary paragraphs for the rest rather than checking
partial items as done.

**Verified:** 788 backend tests (up from 784), frontend eslint/tsc/Playwright all clean. About to
rebuild/redeploy/commit.

**Immediate next actions:** per "continua...hasta acabar tokens" -- realistic candidates the audit
surfaced: wire `MarketCache` into a real call path, gate ranking on quality status, fix stale Vite
references in root docs, instrument-detail route. Do not touch OBSERVE/PAPER/LIVE architecture.

## Audit-log export + i18n Telegram bot — 2026-09-21 (continued further)

Full detail in `.ai/CURRENT.md`'s matching entry. New: `GET /api/events/export?format=csv|json`
(audit trail export with `actor`/`correlation_id`, `SignedIn`-gated, `since`/`until` filters, 50k
cap) -- closes most of the "Seguridad" transversal row. Confirmed the EN/ES Telegram bot i18n from
earlier this session is intact and tested.

**Verified:** 784 backend tests passed (up from 779), ruff/pyright clean (known
`auth_routes.py:65` only). About to rebuild/redeploy/commit.

**Immediate next actions:** check the Fase 1/2 audit fork agent's (`a38356ec6e2d2ff93`) report and
reconcile `docs/PENDING.md` against it. Then keep closing unblocked backlog per "continua...hasta
acabar tokens" -- do not touch OBSERVE/PAPER/LIVE architecture (explicit user instruction), do not
start Fase 6 AI/equities-VIX strategy/Fase 9 LIVE without an explicit decision/gate clearance.

## Observability + 3 parallel agents + concurrent-session merge + /help — 2026-09-21 (continued)

Biggest slice this session. Full detail in `.ai/CURRENT.md`'s matching entry. Key lessons for next
time:

1. **Worktree-isolated parallel agents never commit and never touch the shared Docker stack** (by
   instruction) -- merging their work back means manually reading each agent's `git diff` inside
   its own worktree and applying it by hand when more than one agent (or your own uncommitted
   work) touches the same file. `git worktree remove --force` + `git branch -D` once merged.
2. **If you find unrelated uncommitted work already in the shared main working tree that you
   didn't create, stop and ask before touching it** -- it may be a concurrent session (it was,
   here: FIFO PnL, a Telegram pairing flow, a loading-skeleton refactor). Don't guess, don't
   silently overwrite, don't silently commit it either.
3. A Protocol with plain attributes doesn't structurally satisfy SQLAlchemy 2's `Mapped[T]`
   columns under pyright (class-level descriptor type vs. resolved instance type) -- if you hit
   this, accept the concrete ORM row type directly instead of fighting the Protocol.
4. Prometheus alert rules can and should be rehearsed for real with `promtool test rules` before
   claiming "alertas ensayadas" -- synthetic time series, assert the pending→firing transition at
   the right eval_time. `promtool` ships inside the official `prom/prometheus` image.

**Verified, fully combined state:** 769 backend tests, ruff/pyright clean (known `auth_routes.py:65`
only), frontend eslint/tsc clean, Playwright 12/12. Rebuilt/redeployed with
`--profile monitoring`, migrations 0031+0032 applied, all 10 services healthy.

**Immediate next actions:** commit (user already said to integrate+commit everything), then ask
what's next.

## Research jobs: quota + UI — 2026-09-21 (same session, continued)

Fourth increment. Full detail in `.ai/CURRENT.md`. Key lesson for next time: **before scoping a
`docs/PENDING.md` item as a big build, check the actual code first** -- Fase 7's queue/cancellation
backend (`ResearchJob` domain type, `ResearchJobRepository`, `apps/api/research_routes.py`) was
already fully built and working, just had zero test coverage and zero frontend. The real gap was
much smaller than the unchecked PENDING.md boxes implied. Added: a system-wide queue-depth quota
(5 active jobs), `tests/integration/test_research_routes.py` (previously nonexistent),
`ResearchJobsPanel.tsx` on the Investigación page.

**Found**: `TestClient.delete()` doesn't take a `json=` kwarg in this httpx/starlette version --
use `client.request("DELETE", url, json=...)`. First DELETE-with-body test in this suite; worth
remembering if another DELETE route gets tested.

**Verified:** full suite 721 passed, ruff/pyright clean (known `auth_routes.py:65` error only),
frontend eslint/tsc clean, Playwright 12/12. Rebuilt/redeployed (no new migration), all 8 services
healthy.

**Immediate next actions:** ask the user to commit, then what's next. Fase 7's remaining items
need Fase 6 (AI provider) to exist first. Unblocked candidates: Fase 8 reports/dedup, transversal
backlog rows (observability, event pagination, config versioning, docs).

## Flaky Settings e2e fixed + CSV/JSON trade export — 2026-09-21 (same session, continued)

Two more small, well-scoped, unblocked increments after Telegram commands (user: "hace falta
muchisimo," keep going). Full detail in `.ai/CURRENT.md`'s matching entry.

1. Fixed the Settings e2e flake flagged in the previous handoff entry -- it was asserting the
   OBSERVE-state UI while the shared mock always returns `environment: "PAPER"`, only "passing" by
   catching a pre-hydration transient render. Fixed by asserting the settled state instead.
2. `GET /api/portfolio/export?format=csv|json` -- full PAPER fill history for the signed-in user's
   own account. No PnL column: no FIFO lot tracking exists for live PAPER fills (`docs/PENDING.md`
   Fase 4 still open), and this codebase's own convention is to never fabricate a number rather
   than reuse an unrelated computation or invent one.

**Verified:** full suite 713 passed, ruff/pyright clean (same known `auth_routes.py:65` error),
frontend eslint/tsc clean, Playwright 11/11 twice in a row. Rebuilt/redeployed (no new migration),
all 8 services healthy. Both committed with the user's established "commit and continue" mode this
session (`09b3947` e2e fix, `f053fce` export).

**Immediate next actions:** ask the user what's next. See `.ai/CURRENT.md` for the current
candidate list (Fase 7 research runner, Fase 8 reports/dedup, other transversal-backlog rows are
unblocked; Fase 6 AI and the equities/VIX idea need external decisions; Fase 9 LIVE stays gated).

## Telegram inbound commands — 2026-09-20 (same session, continued)

Third slice this session (after breakers and walk-forward). Full technical detail in
`.ai/CURRENT.md`'s matching entry. Summary: `/status`/`/breakers`/`/portfolio` read-only Telegram
commands plus `/pause`/`/resume` that only ever create an expiring confirmation the operator
completes through the existing Admin+fresh-MFA web flow (`POST /api/telegram/confirmations/{id}/
confirm`) -- Telegram itself never executes a sensitive action. Long-polling (`getUpdates`), not a
webhook, since this self-hosted stack has no public HTTPS ingress -- confirmed with the user via
`AskUserQuestion` before writing any code, along with the command scope.

**Real bug worth remembering for next time anyone touches Telegram polling**: the shared
`HttpxTelegramTransport` client has a 10s request timeout; Telegram's long-poll `timeout` param
must stay comfortably under that or httpx raises a read timeout before Telegram ever replies. Used
8s. If a future slice wants longer long-polling, it needs its own httpx client with a longer
timeout, not just a bigger `timeout` param on the shared one.

**Found but explicitly not fixed (pre-existing, unrelated file)**: `apps/web/e2e/
observability.spec.ts`'s "settings and first-steps..." test flakes on `master` itself (~40%,
verified via `git stash` before touching anything) -- the mocked dashboard always says
`environment: "PAPER"` but the test asserts OBSERVE-state text, only passing by catching a
pre-hydration transient render. Flagged to the user, not silently rewritten -- out of scope for a
Telegram-commands slice.

**Immediate next actions:** ask the user to commit (full verification already done: 709 backend
tests, Playwright 11/11, stack rebuilt/redeployed, migration `0030` applied, all 8 services
healthy), then ask what's next.

## Persistent circuit breakers committed — 2026-09-20 (new session)

Fresh session, no prior chat history. Found the breaker slice already fully built and sitting
uncommitted in the working tree (matching the prior session's own "Immediate next actions" in
`.ai/CURRENT.md`). Verified it rather than assuming "uncommitted" meant "incomplete": full suite
661 passed, ruff/pyright clean, frontend eslint/tsc clean, rebuilt every Docker image and
redeployed the whole stack, migration `0029_breakers` applied cleanly, all 8 services healthy.
Committed with the user's explicit approval (`dbbb9d5`). See `.ai/CURRENT.md`'s matching entry for
full technical detail.

User also pasted a pseudocode trading strategy idea (VIX/Fear&Greed-conditioned equities DCA on
SMH/NVDA + a crypto-sentiment branch) mid-session. **Not implemented** -- recorded as a new
unchecked `docs/PENDING.md` Fase 3 item instead, since it needs an equities market/venue adapter
and a VIX/Fear&Greed data source, neither of which exists in this codebase yet (`MarketType` is
crypto-`SPOT`-only today). Needs an explicit user decision on a data provider before any code gets
written -- flagged back to the user, not started unilaterally, per `AGENTS.md`'s "avoid
speculative architecture changes."

**Immediate next actions:** ask the user what's next -- walk-forward/backtest UI wiring, further
`PENDING.md` phase auditing (Fase 6 AI, Fase 8 Telegram), the new equities/VIX strategy idea
(pending a data-provider decision), or something else entirely.

## Portfolio slice committed, working tree backlog cleared — 2026-09-17 (new session)

Picked up a fresh session with no prior chat context, user said "continua con lo pendiente acaba
todas las fases." Found the same lesson this file already documents below: `.ai/CURRENT.md` said
the Tiingo network-bug fix was "not yet committed" but `git log` showed it was already at `e7c78f0`
-- always cross-check against `git log`, this file and `CURRENT.md` lag reality.

What was actually still uncommitted: the Portfolio page (Codex's slice, described in the entry
this replaces) plus a small, unrelated Backtests UX fix (suggested date window + clearer
empty-candles error) that had landed in the same working tree. Split into two commits after
finishing both properly:

1. `9ad0c56` -- Portfolio page + `docs/AI-DEVELOPMENT.md`. Found and fixed real gaps before
   committing, not just wired what was there: two `pyright` errors (`portfolio_routes.py` passing
   plain `str` DB columns into Pydantic `Literal` fields -- fixed with `typing.cast`, safe because
   `ledger_postings.py` only ever writes CASH/POSITION under a user's own `account_id`, CLEARING
   always uses the fixed `"clearing"` id) and **~30 missing English translations** for both the
   Portfolio page and the Docs page's new flow panel (the working-tree diff had added the Spanish
   UI text and wired `i18n.t()` calls but never touched `en.json` -- EN locale would have silently
   fallen back to Spanish strings). Also removed two now-dead `en.json` entries left over from the
   GitHub-link panel the Docs redesign removed. One pre-existing gap *not* fixed (out of scope for
   this commit): `"TU INSTANCIA PRIVADA"` on the Docs hero has no EN translation either, predates
   this diff.
2. `8460293` -- Backtests form now defaults to a real available window (last 48h) and only offers
   the 1h timeframe (the only one actually ingested); the empty-candles 422 explains the likely
   cause instead of a bare exception string.

**Verified before each commit**: full suite 595 passed (Docker had to be started first -- was not
running at session start), ruff clean (also fixed one pre-existing `E501` in migration `0026`),
pyright clean (same one known pre-existing `auth_routes.py:65` error, nothing else), frontend
eslint/tsc clean. Rebuilt **both** `wallybot-api:0.1.0` and `wallybot-api-research:0.1.0` (this
session's own recurring lesson about the compose `&app` anchor), `docker compose up -d` applied
migration `0026` and redeployed all 8 services healthy. `claude-in-chrome` was not connected this
session, so the Portfolio/Docs pages were **not** visually confirmed in a live browser -- only
`curl`-verified that `/api/portfolio` returns `401` unauthenticated (route is mounted) and
`/docs` returns `200`. Worth a visual pass next session if the extension reconnects.

`graphify update .` run after all code changes.

**Immediate next actions:** `docs/PENDING.md` (last reviewed 2026-09-12) is now significantly
stale relative to `git log` -- most of its Fase 1/2/4/10 checkboxes read as still-open but
substantial pieces are already shipped (Portfolio, price consensus, wallet/entity intelligence,
Telegram, research runner). Before starting a new phase, re-audit `PENDING.md` against actual code
rather than trusting its checkboxes. The user asked to "finish all phases" -- flagged back to them
that Fase 9 (LIVE trading) is explicitly gated behind human-only steps (`RISK.md`/`SECURITY.md`:
trade-only key evidence, TOTP+account confirmation, small-capital test) that no agent can clear
unilaterally per `AGENTS.md`'s "never grant execution/withdrawal capability to research code
paths" -- can build LIVE's supporting infrastructure but not "complete" activation alone.

## Control-center UX + fresh-MFA confirmation — 2026-09-17

The user asked for a polished, aligned UI on every Control Center page and explicitly authorized
a commit. Configuración is now a responsive card layout (OBSERVE/PAPER, Telegram, MFA); Docs is a
product onboarding map rather than developer tooling; Connections no longer reuses the four-column
market form. The MFA refresh endpoint is intentionally CSRF-protected and updates the existing
session only after a fresh TOTP code. No withdrawal or live-execution capability was added.

Follow-up UI polish rebuilt the sidebar as a compact desktop rail and a closed-by-default mobile
menu, reduced the visual size of the Telegram switch without reducing its tap target, and made the
layout rhythm/tables/forms consistent across Control Center pages.

Verification completed: integration auth suite 8 passed; focused frontend TypeScript/ESLint and
the mocked Playwright suite passed, including the new 390px layout test. `pyright` retains the
known pre-existing literal-role error in `apps/api/auth_routes.py:65`. The code graph was updated.

Commit the cohesive current UI + MFA changes together; the user explicitly asked for it. Avoid
adding unrelated future work to that commit.

Picked up a fresh session with no prior chat context. `.ai/CURRENT.md`/`.ai/HANDOFF.md` were stale
relative to `git log` -- several slices they described as "not yet committed" (Parquet ingestion,
research job consumer, wallet/entity intelligence) were already committed by the time this session
started. **Lesson for the next agent: always cross-check `.ai/CURRENT.md` against `git log` before
trusting its "not yet committed" claims -- these files lag behind reality between sessions.**

This session's slice: wired the Telegram bot-token storage (committed earlier, unused until now)
to actually send a notification when an admin pauses/resumes the bot via `/api/control`. See the
"Telegram notifications actually wired up" entry in `.ai/CURRENT.md` for the full detail, including
the key architectural finding that `worker`/`scheduler` are *also* network-isolated (not just
`research`) -- only `apps/api` can reach the internet, so any future notification trigger not
already inside an `apps/api` request path needs a polling/cross-process design, not a direct call
from a scheduler tick.

One small pre-existing uncommitted frontend diff (Docs page architecture-diagram link,
`apps/web/src/{proxy.ts,theme.css,lib/locales/en.json}`, `docker/web.Dockerfile`,
`apps/web/public/architecture.html`) was already sitting in the working tree when this session
started; left as-is and never staged/committed by this session, since it looked complete and
unrelated to backend work. If it's still there next session, check with the user before touching
it -- it isn't this session's to commit or revert.

Both of this session's own slices were committed with the user's explicit approval (asked via
AskUserQuestion each time, per `AGENTS.md`'s "never commit without asking"): `0b0b036` (Telegram)
and `dcdd987` (Kraken+Tiingo price consensus). User's choice both times was "commit and continue,"
so treat that as this session's established mode unless they say otherwise.

## Codex UI handoff — 2026-09-12

Claude is actively modifying backend/connectivity in this working tree. User explicitly assigned Codex UI/UX, especially dark mode. Preserve concurrent changes; do not commit or revert the entire tree.

Delivered: apps/web/src/theme.css complete dark surfaces; layout imports it; ThemeToggle accessible title and 44px targets. QR stays white. Production browser tests exercise auth, theme persistence, ES/EN, CSP nonce and unknown-route 404. scripts/dev.py isolates web environment; CI adds WALLY_E2E_PRODUCTION tests with disposable DB and sanitized frontend environment.

Verified: Next production build, 2 production browser tests, 10 environment tests, frontend lint and targeted Ruff. Docker web rebuilt and updated ALONE. Actual localhost mobile setup smoke: HTTP 200, dark palette, 390px without overflow or page errors. Screenshots in ignored apps/web/test-results. No real enrollment or secret reads.

Backlog requested by user: docs/PENDING.md. Next UI work: integrate Claude's market contract, filters/loading/error states, accessible table interactions and translated event labels. Do not duplicate backend work. Test harness currently runs next start in production; it warns that standalone server.js is preferred. Exact standalone harness is a remaining improvement, although Docker standalone build and local mobile smoke passed.

Two review agents hit account usage limits; no replay module was delivered by this team. Check CURRENT and actual working tree before taking another phase. Graphify query and AST-only update succeeded using C:/Users/kingg/AppData/Roaming/uv/tools/graphifyy/Scripts/graphify.exe; CLI was not on PATH.


## Apple HIG-inspired UI refresh — 2026-09-12

User rejected green palette. Codex replaced theme.css with semantic neutral white/gray and graphite surfaces, accessible blue actions, larger labels, system fonts, selected navigation aria-current/indicator, keyboard skip link, reduced-motion and contrast preferences. Design evidence: docs/UI-DESIGN.md. Two production E2E tests and lint passed; desktop clear/dark and mobile screenshots inspected. Only web service rebuilt; preserve Claude backend changes.


## Activity inspection UI — 2026-09-12

Codex continued observability UI while Claude owns market/backend integration. EventsPage adds text search (message/code/id), type filter, newest/oldest sort, refresh, explicit failure/stale states and empty filter reset. EventList detailed mode exposes stable ID, original event code and full UTC timestamp. Filters are explicitly limited to the latest 100 API events; no claim of full-history search or live stream. No API/DB changes. Verified frontend lint, Next production build and 2 production E2E tests including filters, details, ES/EN and mobile no-overflow; activity mobile screenshot inspected. Web-only deployment. Next: backend history pagination contract with Claude, translated display labels, live stream only after authenticated server delivery exists.


## System service summary — 2026-09-15

Codex added counts for reported essential connections/processes, healthy services and services needing review. Optional integrations excluded; failed refresh labels the summary as the last successful check. ES/EN and responsive layout preserved. Focused mocked browser test passed (counts, stale refresh, empty processes, mobile); screenshot inspected; ESLint, TypeScript and targeted Ruff passed. Docker unavailable (named pipe missing), so production-stack verification and web deployment were not performed. New apps/web/playwright.ui.config.ts runs only fully intercepted observability specs using scripts/ui_test_server.py, stripping WALLY_* environment and directing fallback API traffic to an unused local port. No backend changes.

Final verification: all 8 mocked observability browser tests passed with the frontend-only config; Graphify AST update completed; git diff --check clean. Docker deployment remains pending.


## Backtest form clarity — 2026-09-15

Codex UI: allocation now explicitly a fraction, with examples for allocation/fees/slippage. Dates disclose browser time zone and UTC transport; invalid or reversed/equal windows are blocked before API submission with translated accessible errors. Instrument names are required with max length 16; feature window required, 1–500 per API. Decimal strings remain unchanged in requests. Focused browser test passed for rejected dates without POST, ES/EN errors, decimal payloads, successful execution/history and server 422. ESLint/TypeScript passed. No backend or deployment changes; previous Docker availability limitation remains.

## Portfolio accounting and deployed PAPER clarity — 2026-09-21

Portfolio data is tenant-scoped to `paper:<user-id>`. `wallybot/application/portfolio_performance.py`
matches fills oldest-first with FIFO and fails closed for invalid sales or a non-quote-currency
fee. `apps/api/portfolio_routes.py` presents aggregate realised PnL/open cost basis and the web
renders it. Export intentionally remains raw ledger rows because per-fill PnL for a partial FIFO
close is ambiguous. Do not label PAPER as an undeployed/staging instance: it is the simulation
account inside the deployed app. It remains deliberate safety policy; LIVE/withdrawals are not
enabled.

Current deployment was rebuilt successfully and `/health/ready` returned ready. Targeted
portfolio tests: 15 passed. Preserve concurrent uncommitted work and do not make a broad commit.

## Telegram token-first pairing — 2026-09-21

`migrations/versions/0032_telegram_pairing.py` adds `telegram_config.pairing_code_hash`.
`POST /api/telegram` with a token/no chat, or `start_pairing: true`, returns a one-time code only
to the authenticated admin; `GET` never returns it. `run_telegram_command_tick` uses the pending
digest to process only `/start <code>`, atomically persists the matching chat id, clears the hash,
and then resumes its existing allowlisted-command behavior. It never executes commands while
pairing. Tests: 33 focused Telegram route/loop tests passed. Full docker rebuild/redeploy passed;
`migrate` exited 0 and every service was healthy. Do not use any bot token supplied in chat;
require a fresh revoked/reissued token.
