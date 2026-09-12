# Decisions

Durable technical/architectural decisions for **this repo only** (wally-bot). This file must never
be merged with or copied from another repository's decisions.

For the actual product/architecture decisions (Python, PostgreSQL, Redis, exchange adapters,
historical storage, modular monolith, AI/risk separation, order idempotency, port 3333 gateway,
ledger+outbox, bootstrap/LIVE gating, runtime base image), see `docs/adr/` — those are the real
ADRs for this project. This file is only for decisions about the *AI tooling* itself.

## 2026-09-12 — AI tooling bootstrapped without `.git`

**Context:** This repo has no `.git` folder despite being a substantial, clearly intentional
project (pyproject.toml, `apps/`, `wallybot/`, migrations, docker-compose, extensive docs, CI
config, pre-commit config).

**Decision:** Did not run `git init`. Configured Serena, Graphify (code-only graph, no git hooks),
`AGENTS.md`/`CLAUDE.md`, `.ai/`, and specialized agents anyway, since none of those strictly
require git. Flagged the missing `.git` in `.ai/CURRENT.md` and `docs/AI-DEVELOPMENT.md` instead
of silently fixing it.

**Why it matters:** If `.git` shows up later (user runs `git init` or restores it from elsewhere),
re-run `graphify hook install` to get git-synced graph updates, and start actually using the
`git status`/`git diff` steps in `AGENTS.md`.

## 2026-09-12 — Codex specialized agents are Skills, not `.codex/agents/*.md`

Same finding as the sibling `ai-shared-stack` scaffold repo: the installed Codex CLI has no
`.codex/agents/` mechanism. Verified via `~/.codex/skills/.system/review-agent/` — the real format
is a Skill (`SKILL.md`) + `agents/<id>.yaml` interface manifest. Used that here too.

## 2026-09-12 — Secrets explicitly excluded from all code-intelligence tools

**Context:** `.secrets/` (bootstrap token, DB passwords/URLs, encryption/backup keys) and `.env`
are gitignored. Serena defaults to `ignore_all_files_in_gitignore: true`; Graphify's scan output
and the resulting `graph.json` were checked and confirmed to contain zero references to any
`.secrets/*` filename or path.

**Decision:** Left Serena/Graphify on their default ignore behavior — no explicit `ignored_paths`
override was needed. Do not add one that would re-include `.secrets/`/`.env`.

## 2026-09-12 — Stale nginx config caused a duplicate CSP header (Vite→Next.js migration)

**Context:** After fixing `apps/web/package.json` to actually run `next build` (it was still
calling the uninstalled `vite`) and rebuilding the `wallybot-web` image, the app loaded but Chrome
blocked every inline script with a CSP violation. Direct `curl -sD -` against the gateway showed
**two** `Content-Security-Policy` response headers: the correct one from `proxy.ts` (per-request
nonce + `strict-dynamic`), and a second, static one (`script-src 'self'`, no nonce) that has no
match anywhere in `docker/gateway.conf` on disk. Browsers AND multiple CSP headers together
(logical AND), so the second one blocked everything the first one allowed.

**Root cause:** `docker/gateway.conf` is bind-mounted read-only into the nginx container; nginx
only reads it at process start (or on `nginx -s reload`), not on every request. The gateway
container had been running for hours since before `gateway.conf` was last edited (it used to carry
a static CSP for the old Vite SPA, which had no way to do per-request nonces) — so nginx was still
enforcing the old in-memory policy even though the file on disk was already correct. `docker exec
wallybot-gateway-1 cat /etc/nginx/conf.d/default.conf` looked fine and was misleading for this
exact reason.

**Fix:** `docker exec wallybot-gateway-1 nginx -s reload` (or a full container recreate) after any
`gateway.conf` edit — a bind mount does not imply nginx will pick up the change.

**Why it matters:** Any future edit to `docker/gateway.conf` needs an explicit nginx reload/restart
of the `gateway` service to take effect; comparing the file on disk to nginx's actual behavior
without reloading will look like a bug in the file when the file is already correct.

## 2026-09-12 — next-themes' injected script needs an explicit `nonce` prop

**Context:** After fixing the gateway CSP above, one inline script was still blocked — traced by
matching its CSP-reported `sha256-` hash to next-themes' anti-flash script (the one that sets
`class="dark"`/`"light"` on `<html>` before hydration to avoid a flash of wrong theme).

**Root cause:** Next.js's documented "automatic nonce propagation" (extracting the nonce from the
`Content-Security-Policy` response header and stamping it onto inline scripts) only covers scripts
Next.js itself generates internally — not a third-party library's own `dangerouslySetInnerHTML`
script rendered inside the tree, even though it's part of the same SSR pass.

**Decision:** Pass `nonce={(await headers()).get("x-nonce")}` explicitly to `<ThemeProvider>` in
`apps/web/src/app/layout.tsx` (`proxy.ts` already forwards `x-nonce` on the request). Confirmed via
Context7 docs (`pacocoursey/next-themes`) that `ThemeProvider`/`ThemeScript` accept a `nonce` prop
for exactly this case.

**Why it matters:** Any future library that injects its own inline `<script>`/`<style>` under this
strict per-request-nonce CSP will need the same treatment — check whether it accepts a `nonce`
prop before assuming Next.js's automatic propagation covers it.

## 2026-09-12 — Repo-wide DTO/DRY/SOLID/KISS/Clean Architecture refactor pass

**Context:** User explicitly requested applying these principles across `apps/web` and the backend.
Before planning, read the actual backend (`wallybot/security/auth.py`, `wallybot/domain/control.py`,
`apps/api/*.py`) and frontend (`Application.tsx`, `lib/api.ts`, `Auth.tsx`, `Dashboard.tsx`) to find
real gaps rather than inventing structure — see the approved plan at commit history around this
entry for the full reasoning.

**Decision — what changed:**
- Backend: added `apps/api/dto.py` (explicit Pydantic **response** DTOs, `response_model=` on every
  route), separate from `apps/api/schemas.py` (request DTOs) — input/output validation change for
  different reasons, so they're different files. Added `apps/api/cookies.py` (`set_cookie`/
  `clear_cookie`) to remove a duplicated inline `response.delete_cookie(...)` in `logout`.
- Frontend: split `lib/api.ts` into `lib/dto.ts` (Zod schemas, matching the backend DTO naming) and
  `lib/api-client.ts` (pure transport: `api()`, `ApiError`, `setCsrf`). Split `Dashboard.tsx` (543
  lines mixing data-fetching + a 6-view state machine + presentation) into
  `hooks/useDashboardData.ts` + `components/dashboard/{DashboardShell,Service,EventList,pages/*}.tsx`.
  Split `Auth.tsx` (338 lines, same pattern) into `hooks/useAuthFlow.ts` +
  `components/auth/{CredentialsForm,MfaForm,RecoveryCodes}.tsx`. No visual, copy, or DOM-structure
  changes — same classNames/i18n keys throughout.

**Decision — what deliberately did NOT change, and why:** `wallybot/security/auth.py`
(`AuthService`), `crypto.py`, `throttle.py`, `wallybot/domain/control.py` were left untouched.
`AuthService`'s methods are already SRP-cohesive (one bounded context: auth-flow transactions, all
changing for the same reason) — splitting it into multiple service classes or adding a
repository/UnitOfWork abstraction would be over-engineering that contradicts KISS and
`ARCHITECTURE.md`'s own "create modules when a real capability needs them" rule, while adding real
regression risk to tested Argon2id/TOTP/session/CSRF logic with no concrete defect being fixed.

**Verification:** `uv run pytest tests/unit tests/integration tests/property` (23 passed, unchanged
response shapes just now validated) + `pnpm lint` + `pnpm build` + full `pnpm test:e2e` (the
existing `foundation.spec.ts`, covering setup→MFA→dashboard→pause/resume→activity→system→mobile→
logout→recovery-login end to end against a disposable testcontainers stack) — all green, confirming
byte-identical behavior after the split.

**Why it matters:** A git safety checkpoint (`b15a0dc`, this repo's first commit) was made
specifically before this refactor so it's fully reversible if something surfaces later. If asked to
extend DTOs/layering further, follow the same rule: only split what's genuinely doing more than one
job, and always re-run the full verification chain above (not just `pytest` or just `pnpm build`
alone) before considering it done.

## 2026-09-12 — Always run `pip-audit` right after adding a new Python dependency

**Context:** Phase 2 Slice 5 needed a Parquet writer, so `pyarrow` was added
(`user confirmed via AskUserQuestion, chose pyarrow over polars/deferring`). The first `uv sync`
resolved `pyarrow==20.0.0`. Running `uv run pip-audit` immediately after (not as an afterthought)
found a known CVE (`PYSEC-2026-113`) in that exact version, fixed in `23.0.1`.

**Decision:** Tightened the `pyproject.toml` constraint to `pyarrow>=23.0.1,<26`, re-ran
`uv sync` (resolved `25.0.1`), re-ran `pip-audit` (clean) and the full test suite (still green)
before committing.

**Why it matters:** `uv add`/editing `pyproject.toml` directly picks whatever satisfies the stated
range — it does not know about CVEs. `pip-audit` is listed in `TESTING.md`'s static/security gate
for exactly this reason, but it is easy to treat as a CI-only concern and skip locally. Any future
new dependency in this repo must get a `pip-audit` pass in the same turn it is added, before the
commit that introduces it — not deferred to whenever CI happens to run.

## 2026-09-12 — Kraken's public market-data endpoints need no API key

**Context:** Phase 2 Slice 6 (real Kraken adapter) was assumed blocked on the user providing
Kraken API credentials, and the user was asked for them / asked to confirm skipping to Phase 3
instead. The user pushed back ("que es kraken tu puedes obtenerlas no?"), prompting an actual
check rather than continuing on the assumption.

**Finding:** `curl https://api.kraken.com/0/public/{AssetPairs,OHLC,Ticker}` all work with zero
authentication — Kraken's market-data endpoints are public. Only trading/balance endpoints
(Phase 4 territory, a different capability entirely) need an API key. This session also had real
outbound network access, verified directly rather than assumed.

**Decision:** Built `wallybot/exchanges/kraken.py` (`KrakenExchange`) against the public REST API
with no credential handling at all, immediately, in the same turn. Contract-tested it against real
recorded responses (`tests/contract/test_kraken_exchange.py`), then separately verified the real
`HttpxKrakenTransport` production path live against the actual API outside the test suite.

**Why it matters:** Don't assume a third-party integration needs credentials without checking that
exchange's actual API documentation/behavior first — "market data" and "trading" are frequently
gated at very different authentication levels, and conflating them can block real, buildable work
for no reason. If a future task looks blocked on "needing an account/API key," verify the specific
endpoints actually required before asking the user for anything.
