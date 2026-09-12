# ADR-003: Redis is disposable acceleration

Status: accepted for design, 2026-09-09.

Context: snapshots and notifications need low latency without risking ledger loss.

Decision: Redis caches validated data and wakes durable DB-backed jobs. Financial reservations, idempotency and job truth remain in PostgreSQL.

Alternatives: Redis-only queues/locks simplify delivery but can lose authoritative work or exclusion on failure. A separate message broker adds operational cost before demonstrated need.

Consequences: DB scans recover lost wakeups; all consumers tolerate duplicates. Cache expiry never implies valid fresh market data.
