# ADR-008: Durable intent and reconcile-before-retry

Status: accepted for design, 2026-09-09.

Context: a timeout cannot distinguish rejection from an accepted exchange order.

Decision: persist stable client IDs and scoped unique idempotency keys before submission. Claim intent, record SUBMITTING, submit, then persist observed status. Ambiguity enters UNKNOWN, retains reservations and reconciles before retry.

Alternatives: blind HTTP retries can duplicate trades; claiming exactly-once external execution from a database transaction is unsound.

Consequences: unresolved ambiguity may require operator intervention and blocks new risk. Adapter lookup and negative-result semantics require tests. Cancellation also needs confirmation and racing fills remain valid.
