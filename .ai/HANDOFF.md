# Claude handoff — 2026-09-16 (new session)

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

**Not yet committed** — the working tree had one small pre-existing uncommitted frontend diff
(Docs page architecture-diagram link, `apps/web/src/{proxy.ts,theme.css,lib/locales/en.json}`,
`docker/web.Dockerfile`, `apps/web/public/architecture.html`) when this session started; left as-is
since it looked complete and unrelated. This session's own backend changes (telegram wiring) are
also uncommitted — ask the user before committing either.

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
