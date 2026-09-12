# ADR-010: Balanced ledger and transactional delivery

Status: accepted for design, 2026-09-09.

Context: fills, positions and events must remain coherent after crashes.

Decision: deduplicated fills, per-currency balanced journal postings, projections and outbox records commit atomically. Corrections reverse postings. Consumers deduplicate at-least-once deliveries.

Alternatives: reconstructing history from current balances loses provenance; direct event publishing before commit can announce nonexistent fills.

Consequences: ledger constraints and crash tests are mandatory. Exchange reconciliation resolves discrepancies without silently replacing history. Actual-fill PnL already includes price impact, so slippage attribution is not deducted twice.
