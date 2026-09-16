# ADR-015: Per-user investment workspaces and secret isolation

Status: accepted for design, 2026-09-16.

## Context

WallyBot must serve independent users. Every user may connect different wallets, exchanges,
brokers and intelligence/AI providers, set a different investment mandate, run independent
research or periodic analysis, and see only their own portfolio, activity and decisions. Public
market data and charts can be shared because they contain no account information.

## Decision

- Introduce an immutable `workspace_id` owned by a user. Accounts, provider connections,
  encrypted credentials, wallet addresses, portfolio snapshots, orders, fills, decisions,
  research jobs, AI usage/budgets, notifications and audit events belong to exactly one workspace.
- Every private read/write repository takes workspace identity from authenticated server-side
  context, never from a client-supplied filter. Database foreign keys, composite uniqueness and
  row-level security enforce the same boundary. An administrator does not receive implicit access
  to another user's investment data.
- One logical worker queue is scoped by workspace/account with a concurrency and budget limit per
  workspace. A job claim carries workspace identity; it cannot read another workspace's secrets,
  positions or artifacts. Separate processes/container replicas may be introduced for scale, but
  process separation does not replace database/secret authorization.
- Provider credentials and user-supplied intelligence/agent tokens are encrypted at rest with
  envelope versioning, write-only from the browser and decrypted only in the matching scoped
  adapter. They are redacted from logs, events, exports and API responses. Tokens are never put in
  a URL, browser storage, analytics or research artifacts.
- Public market connectors publish normalized, source-attributed and freshness-labelled data that
  all workspaces can view. Any cached quote is public-only; balances, positions, orders and PnL
  are workspace-private.
- Each workspace configures its own allowed providers, wallet/watchlist, asset/token eligibility,
  copy-signal sources, AI model/provider, cost budget, analysis cadence, risk policy and
  execution mode. New configurations default to read-only/OBSERVE; PAPER, then trade-only LIVE,
  are promoted only through the existing gates.
- All external trading credentials must be account-scoped and trade-only with withdrawals and
  transfers disabled. WallyBot has no cross-workspace credential delegation and no withdrawal API.

## Consequences

The Connections, Portfolio, Wallets, Tokens, AI/Intelligence, Activity, Research and Settings
pages become workspace-scoped. Markets and charts remain common, with provider/source selection
visible. Existing single-tenant tables and routes must be migrated deliberately; merely adding a
`user_id` column without foreign keys, RLS, scoped uniqueness and negative isolation tests is not
acceptable.
