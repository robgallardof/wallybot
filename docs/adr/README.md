# Architectural decision records

Accepted for the design baseline; runtime evidence remains pending. Supersede a record with a linked ADR rather than silently rewriting a significant decision.

| ADR | Decision |
| --- | --- |
| [001](001-python.md) | Python and typed domain boundaries |
| [002](002-postgresql.md) | PostgreSQL financial authority |
| [003](003-redis.md) | Redis as disposable acceleration |
| [004](004-exchange-adapters.md) | CCXT behind constrained adapters; feed evaluation |
| [005](005-historical-storage.md) | Parquet and DuckDB |
| [006](006-modular-monolith.md) | Modular monolith, isolated processes |
| [007](007-ai-risk-separation.md) | Advisory AI, deterministic risk veto |
| [008](008-order-idempotency.md) | Durable intents and ambiguity reconciliation |
| [009](009-port-3333-gateway.md) | Single application origin and hybrid exception |
| [010](010-ledger-and-outbox.md) | Balanced ledger and transactional outbox |
| [011](011-bootstrap-and-live.md) | Protected bootstrap and explicit LIVE rearm |
| [012](012-runtime-base.md) | Updated Alpine foundation runtime and security gate |
