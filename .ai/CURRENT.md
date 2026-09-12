# Current task

**Task:** Finish the `apps/web` frontend migration off Vite onto Next.js App Router (Tailwind v4,
Zod, React Hook Form, pnpm, i18next, next-themes) and get the local Docker stack serving it
correctly. Requested by the user in Spanish: "migrar a next js tailwind, zod react forms... pnpm,
i18n... next themes", followed by continuing toward the broader product roadmap.

**Scope:** `apps/web` only (frontend). No backend/domain code touched.

**Branch:** N/A — this directory still has no `.git` folder.

**Progress:**
- Found the App Router migration (layout.tsx, page.tsx, client.tsx, `[section]/page.tsx`,
  Tailwind v4, Zod, react-hook-form, react-i18next, pnpm-lock.yaml) was already ~90% done in the
  source tree, but `package.json` scripts still called `vite`/`tsc -b` (not even installed) —
  fixed to `next dev` / `next build` / `next start`.
- Fixed a real syntax bug in `Dashboard.tsx` (dangling comma broke the `page` const) that blocked
  the build.
- Installed `next-themes@0.4.6`, wired `ThemeProvider` into `src/app/layout.tsx`, added the
  Tailwind v4 class-based dark variant (`@custom-variant dark (&:where(.dark, .dark *));`) to
  `src/style.css`, and added a minimal `ThemeToggle` component next to `LanguageSelector` in
  `Auth.tsx`/`Dashboard.tsx`.
- **Dark mode is only wired at the mechanism level** (toggle works, persists, `dark` class
  applies). The actual visual palette in `style.css` is still hardcoded light-only hex colors —
  a real dark theme redesign is separate, larger follow-up work, not done here.
- Removed the stale `apps/web/dist/` Vite build artifact.
- Rebuilt the `wallybot-web` Docker image (`docker/web.Dockerfile` was already correctly written
  for Next.js standalone output — it just needed a working `pnpm build`) and recreated the `web`
  container.
- Found and fixed a real production bug via actual browser testing (Playwright), not just build
  success — see `.ai/DECISIONS.md` "Stale nginx config double-sent a CSP header" and "next-themes
  needs an explicit nonce prop".
- Verified end-to-end in a real browser against the live Docker stack: `/login` renders clean (0
  console errors besides the expected pre-auth 401 on `/api/auth/me`), theme toggle flips
  light/dark correctly.
- Ran `graphify update .` after the code changes (AST-only, no LLM cost): 610 nodes, 1071 edges,
  57 communities. Community labels are now stale (renamed by hub since membership shifted) —
  run `/graphify --update` with an LLM key, or re-run `/graphify .` labeling step, before relying
  on `GRAPH_REPORT.md` community names again.

**Relevant files:** `apps/web/package.json`, `apps/web/src/app/layout.tsx`, `apps/web/src/style.css`,
`apps/web/src/components/{Auth,Dashboard,ThemeToggle}.tsx`, `apps/web/src/lib/locales/en.json`,
`docker/web.Dockerfile` (unchanged, already correct), `docker/gateway.conf` (unchanged, already
correct — see decisions log for why it still needed a runtime reload).

**Immediate next actions:** User wants to continue toward the broader product roadmap after this
frontend fix — no specific next feature named yet in this session. Check `docs/PHASE_1.md` and
`docs/adr/` for the phase roadmap before picking the next piece of work.
