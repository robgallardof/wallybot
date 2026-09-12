# ADR-002: PostgreSQL is financial authority

Status: accepted for design, 2026-09-09.

Context: concurrent approvals, fills and retries need durable transactional invariants.

Decision: PostgreSQL with unique constraints, foreign keys, account-scoped row locking, decimal money and Alembic migrations. All approval writers follow the same locking protocol.

Alternatives: SQLite is useful for simple applications but does not validate the production concurrency behavior; Redis is not a financial ledger. TimescaleDB waits for demonstrated query needs.

Consequences: dependency outage blocks new execution; integration tests need real PostgreSQL. Transactions do not encompass exchange network calls.
