# ADR-006: Modular monolith with isolated processes

Status: accepted for design, 2026-09-09.

Context: a single 16 GB host needs understandable deployment and strong research isolation.

Decision: shared domain/application code, separate API/trading/scheduler/research entry points, process credentials and resource limits. Keep only `apps/web` for the frontend.

Alternatives: independent microservices add distributed consistency and deployment complexity; one all-purpose process lets research starve trading.

Consequences: enforce import boundaries and DB grants. Shared code does not grant shared privileges. Research concurrency begins at one.
