# ADR-005: Immutable Parquet and DuckDB

Status: accepted for design, 2026-09-09.

Context: historical scans should not compete with financial transactions.

Decision: immutable partitioned Parquet with checksummed manifests, DuckDB research queries and bounded memory/temp storage. PostgreSQL owns metadata and financial history.

Alternatives: storing every tick in PostgreSQL increases operational load; a distributed analytical cluster exceeds initial host resources.

Consequences: publication and corrections require explicit versions. Backup irreproducible datasets and retain manifests/code hashes for reproducibility.
