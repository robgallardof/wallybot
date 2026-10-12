# ADR-007: AI advises; risk decides

Status: accepted for design, 2026-09-09.

Context: probabilistic outputs cannot enforce deterministic portfolio limits.

Decision: provider-neutral, strictly validated advisory output, budgeted finalist analysis and immutable input provenance. Portfolio proposals always pass deterministic risk; executor validates the persisted intent-bound approval.

Alternatives: direct AI order tools or confidence-based sizing violate the required control boundary.

Consequences: malformed/expired AI decisions cannot execute. Provider outage follows an explicit strategy policy. Research agents cannot promote themselves or alter live limits.

**Partially superseded by [ADR-016](016-ai-autonomous-account.md) (2026-09-23)**: a new, separate, opt-in AI-autonomous PAPER account (`apps/ai_worker`) is a named exception to "portfolio proposals always pass deterministic risk" — confirmed twice by the operator after being shown concrete failure scenarios. This ADR's rule still fully applies to the deterministic strategy path (`run_decision_tick`), unchanged.
