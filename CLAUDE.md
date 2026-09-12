@AGENTS.md

## Claude-Code-specific notes

- Custom specialized agents for this repo live in `.claude/agents/`. Use them via the `Agent` tool
  with the matching `subagent_type`.
- Serena, Context7, Playwright, and Codebase Memory are user-scoped MCP servers (`claude mcp
  list`). Graphify is a CLI (`graphify query "..."`), not an MCP server.
- This repo has no `.git` yet — do not run `git init` unless the user asks.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
