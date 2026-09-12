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
