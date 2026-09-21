# Claude handoff — 2026-09-16 (new session)

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
