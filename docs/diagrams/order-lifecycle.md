# Order lifecycle

The state machine records observations, not assumptions about network delivery. FAILED means a definitive failure; an ambiguous submission is UNKNOWN. Cancel intent may be pending while fills continue. Late fills after a cancellation observation are reconciled against authoritative cumulative quantity and retained in history.

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> VALIDATED: Risk approval and reservation
    CREATED --> REJECTED: Invalid proposal
    VALIDATED --> SUBMITTING: Durable claim and revalidation
    VALIDATED --> REJECTED: Expired or invalid approval
    SUBMITTING --> SUBMITTED: Submission response observed
    SUBMITTING --> UNKNOWN: Timeout or crash
    SUBMITTING --> REJECTED: Definitive rejection
    SUBMITTING --> FAILED: Proven pre-submission failure
    SUBMITTED --> ACKNOWLEDGED: Venue confirms
    SUBMITTED --> UNKNOWN: Status unresolved
    ACKNOWLEDGED --> PARTIALLY_FILLED
    ACKNOWLEDGED --> FILLED
    ACKNOWLEDGED --> CANCEL_REQUESTED
    PARTIALLY_FILLED --> PARTIALLY_FILLED: Additional fill
    PARTIALLY_FILLED --> FILLED
    PARTIALLY_FILLED --> CANCEL_REQUESTED
    CANCEL_REQUESTED --> CANCELLED: Confirmed remainder cancelled
    CANCEL_REQUESTED --> PARTIALLY_FILLED: Fill or cancel rejection
    CANCEL_REQUESTED --> ACKNOWLEDGED: Cancel rejected with zero fills
    CANCEL_REQUESTED --> FILLED: Fill wins race
    CANCEL_REQUESTED --> UNKNOWN: Ambiguous cancel
    UNKNOWN --> ACKNOWLEDGED: Lookup resolves
    UNKNOWN --> PARTIALLY_FILLED: Lookup resolves
    UNKNOWN --> FILLED: Lookup resolves
    UNKNOWN --> CANCELLED: Lookup resolves
    UNKNOWN --> REJECTED: Definitive venue evidence
    UNKNOWN --> VALIDATED: Proven absent and safe retry after risk
    FILLED --> [*]
    CANCELLED --> [*]
    REJECTED --> [*]
    FAILED --> [*]
```
