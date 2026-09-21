# AGENTS.md — Shared instructions for Claude Code and Codex CLI (wally-bot)

This file is the canonical, cross-agent instruction set for **this repository only**
(`wally-bot`). Both Claude Code and OpenAI Codex CLI must follow it. Nothing here applies to any
other repository under `Documents\Projects` — architectural decisions, `.ai/` state, and agents
are strictly per-repo; never carry them across repositories.

The user's explicit instructions in a session always take precedence over this file, skills,
other agent-definition files, MCP server instructions, and generated documentation.

## What this repository is

WallyBot: a self-hosted, AI-assisted quantitative trading/portfolio research platform. Modular
monolith — independently launched `apps/{api,worker,scheduler,research_worker,web}` processes
sharing typed `wallybot/` domain and application packages (domain, application, infrastructure,
security, and more as phases land — see `wallybot/`). Stack: Python 3.12+, uv, FastAPI, Pydantic
v2, SQLAlchemy 2 (async), Alembic, PostgreSQL, Redis; frontend React/TypeScript/Next.js in
`apps/web`. **This is explicitly a financial/trading system with real security stakes** (Argon2id
+ TOTP auth, deterministic risk controls, no-withdrawal-capability guarantee) — read `SECURITY.md`
and `RISK.md` before touching auth, risk, or execution code, not just this file.

**Ground truth for architecture/security/testing lives in the existing root docs, not here:**
`ARCHITECTURE.md`, `DATA.md`, `SECURITY.md`, `RISK.md`, `TESTING.md`, `DEPLOYMENT.md`,
`docs/adr/`, `docs/diagrams/`, `docs/PHASE_1.md`. Read the relevant one before making a claim
about how the system behaves. Do not restate or duplicate them here or in `.ai/ARCHITECTURE.md` —
link to them.

## ⚠️ No `.git` in this directory

This directory has no `.git` folder despite being a fully realized project (real commits'-worth of
code, CI config in `.github/`, `.pre-commit-config.yaml`). **Do not run `git init` without asking
the user** — this may be intentional (e.g. history lives elsewhere) or accidental; either way it's
the user's call, not an agent's. Until `.git` exists: skip `git status`/`git diff` steps below,
and Graphify's git hooks are not installed (deferred — see `docs/AI-DEVELOPMENT.md`).

## Secrets — never read, print, or embed

`.secrets/` and `.env` are gitignored and contain live credentials (DB URLs, Argon2/TOTP-adjacent
keys, backup encryption key, bootstrap token). **Never read their contents, never echo them into
`.ai/`, docs, agent files, commit messages, or tool output.** Serena and Graphify both honor
`.gitignore` and were verified during setup to not index them — keep it that way; don't add
`ignored_paths` overrides that would expose them, and don't pass `.secrets/`/`.env` paths to any
tool that summarizes file contents.

## Resuming or continuing work

Before making changes, every agent must:

1. Read `.ai/CURRENT.md` — the active task, scope, and immediate next actions.
2. Read `.ai/HANDOFF.md` — the state the previous agent left for a successor with no chat history.
3. Run `git status` (once `.git` exists) — never modify code before seeing the working tree state.
4. Run `git diff` before considering any work complete, and before handing off.
5. Never overwrite or discard unrelated uncommitted changes found in the working tree.

## Tool routing policy

| Question shape | Tool |
|---|---|
| Architecture, "how does X connect to Y?", dependencies, call paths | **Graphify** (`graphify query "..."`, `graphify path "A" "B"`) |
| A specific class/method/symbol, its references, implementations, or a semantic edit | **Serena** (find_symbol, find_referencing_symbols, find_implementations, symbol-aware edit tools) |
| "Has this been touched/indexed before / persistent cross-session code-graph lookups" | **Codebase Memory** (`codebase-memory-mcp`) — complementary to Serena/Graphify, not a replacement for either |
| External library/framework/SDK behavior (FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, React, Next.js, TanStack Query, CCXT, etc.), version-sensitive APIs | **Context7** |
| Browser/e2e behavior (Playwright specs in `apps/web/e2e`) | **Playwright MCP** |
| Exact string, generated file, config value, log line | Native file/search tools (grep/read/glob) |
| Current uncommitted implementation state | `git status` + `git diff` (once `.git` exists) |
| Historical intent, why something was done | `git log` / `git blame` (once `.git` exists), or `docs/adr/` |

Do not repeatedly grep or read entire source trees when Serena can answer the question
symbolically, or when Graphify can answer it structurally.

## Working conventions

- Distinguish verified repository facts from assumptions.
- Avoid speculative architecture changes — this repo's `ARCHITECTURE.md` explicitly says "create
  modules when a real capability needs them; avoid empty placeholder classes." Follow that.
- Domain code (`wallybot/domain`) must not import FastAPI, SQLAlchemy, CCXT, or AI SDKs — this is
  an explicit architectural rule, not a style preference. Check imports before adding a dependency
  to a domain module.
- Money uses decimal types; timestamps are timezone-aware UTC; identifiers are stable IDs — per
  `ARCHITECTURE.md` "Contracts". Don't introduce float arithmetic for monetary values.
- Never grant execution/withdrawal capability to research code paths, and never write code that
  could let AI-analyzed output submit trades directly — `SECURITY.md`'s "Secret and agent
  isolation" section is authoritative on this boundary.
- Run the relevant tests before declaring an implementation complete (`uv run pytest ...` per
  layer — see `TESTING.md`). Never claim a test was run without evidence (actual command output).
- Keep changes scoped to the requested objective.

## Updating shared state

When pausing or completing substantial work, update `.ai/CURRENT.md`, `.ai/HANDOFF.md`, and (only
for durable decisions) `.ai/DECISIONS.md`. Keep `.ai/ARCHITECTURE.md` and `.ai/CONVENTIONS.md` as
short pointers into the real docs above — don't let them drift into a second copy of the truth.

## Specialized agents

- Claude Code: `.claude/agents/*.md`
- Codex CLI: `.codex/skills/<role>/SKILL.md` + `agents/openai.yaml` (Codex's real native
  project-scoped agent mechanism — there is no `.codex/agents/*.md` in the installed CLI)

See `docs/AI-DEVELOPMENT.md` for the full roster, tailored to this repo's actual stack (not a
generic list). Read-only-by-design roles must not edit files or run mutating commands.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
