# Phase 12 implementation backlog: AI strategy engine and TradeProposal

Status: Slices 1-3 delivered 2026-09-13. Per ARCHITECTURE.md's implementation sequence: "AI strategy
engine producing schema-validated `TradeProposal`s, wired into the existing
`RiskEngine`/`PortfolioAllocator`/`ExecutionService` pipeline; SHADOW mode before any LIVE
eligibility." Each slice gets its own design pass when started, same discipline as
`docs/PHASE_4.md`/`docs/PHASE_10.md`/`docs/PHASE_11.md` — completing the backlog table does not
mean every dimension ARCHITECTURE.md's "AI strategy layer and TradeProposal" section names is
implemented; each slice's "Explicitly not built" section is the honest record of what is still
open.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | `TradeProposal` domain type + `AIProvider` port (pure, no persistence, no wiring) | Unit + property tests |
| 2 | `FakeAIProvider` + insert-only persistence/audit trail (signals fired, evidence, model output) | Unit tests; integration tests for insert-only history |
| 3 | SHADOW mode + wiring `TradeProposal` → `RiskEngine` → recorded-but-not-submitted outcome | Integration tests: a SHADOW proposal never reaches `ExecutionService.submit`, its would-be `RiskAssessment` is still persisted |
| 4 | Real `AIProvider` adapter (Anthropic/OpenAI) with typed read-only tool surface | Blocked: needs a provider API key with an explicit budget the user authorizes for this purpose — SECURITY.md's "Secret and agent isolation" boundary means this is not a decision to make silently |

**This session implements Slices 1-3.**

## Delivered: Slice 1 — `TradeProposal` domain type + `AIProvider` port

Per ARCHITECTURE.md's Contracts table: "`AIProvider.analyze(context) -> TradeProposal`: Structured,
schema-validated advisory result; the AI's only output artifact; no execution capability." And
from "AI strategy layer and TradeProposal": "an AI model is an analyst and strategy generator,
never an executor... Invalid or malformed model output fails closed: it cannot become an
executable recommendation."

- `wallybot/domain/trade_proposal.py` (pure, no framework imports): `TradeDirection` (LONG/SHORT);
  `AIAnalysisContext` (instrument, features, regime, the strategy signals already computed for
  this instrument, as_of) — deliberately the same validated inputs `Strategy.evaluate` already
  consumes, not a second unvetted data path; `TradeProposal` — every field ARCHITECTURE.md's
  Contracts entry names verbatim (asset/market via `instrument`, direction, strategy, confidence,
  suggested allocation/entry/stop/take-profit, time horizon, signal TTL, reasons, risks,
  supporting signal IDs, invalidating conditions, source event IDs, model ID, prompt version).
  `__post_init__` enforces: confidence and allocation percentage in valid ranges, all prices
  positive, stop/take-profit ordered correctly relative to entry for the given direction (a LONG
  stop above entry, or a SHORT take-profit above entry, is rejected outright rather than accepted
  and silently mis-executed later), positive time horizon and TTL, and non-empty `reasons` — the
  same "every decision needs evidence" rule `RiskAssessment` already enforces.
- `AIProvider` Protocol: `analyze(context) -> TradeProposal | None`. Returns `None` — not a
  fabricated placeholder proposal — when the model has no actionable idea or its raw output fails
  schema validation; callers must treat `None` as HOLD, exactly as RISK.md already requires for
  AI-required strategies when AI is unavailable.
- `wallybot/intelligence/fake_ai.py`: `FakeAIProvider` — returns only what it is seeded with (one
  scripted `TradeProposal` per instrument, or `None`), same shape as `FakeWalletIntelligenceProvider`
  and `FakeSecurityAnalysisProvider`. No real LLM call, no API key needed.
- `tests/unit/test_trade_proposal.py`: every validation rule above, both directions.
- `tests/property/test_trade_proposal_invariants.py` (Hypothesis): arbitrary valid stop/take-profit
  orderings for a given direction always construct; any single field pushed out of its valid range
  always raises.
- `tests/unit/test_fake_ai_provider.py`: seeded proposal returned verbatim; unseeded instrument
  returns `None`, never a fabricated default.

**Explicitly not built in this slice** (each is a separate, later slice above, not a silent gap):
persistence/audit trail of proposals and their evidence (Slice 2); any wiring into `RiskEngine`,
`PortfolioAllocator`, `ExecutionService` or `DecisionPipeline` — a `TradeProposal` today has zero
ability to cause any effect anywhere in the running system (Slice 3, gated behind SHADOW mode);
the typed read-only AI tool surface ARCHITECTURE.md names (`get_market_snapshot`,
`get_wallet_activity`, `get_smart_money_signals`, `get_token_security`, `get_portfolio_state`,
`get_strategy_performance`, `create_trade_proposal`) and the corresponding SECURITY.md allow/deny
list update it calls for; any real model adapter, cost/token accounting or budget enforcement
(Phase 6 was never built — there is no `AIProvider` cost-tracking infrastructure to reuse yet);
`SHADOW` as an actual `Status`/mode value anywhere in `wallybot/domain/control.py` or the execution
pipeline.

## Delivered: Slice 2 — insert-only persistence/audit trail

Per ARCHITECTURE.md: "Every `TradeProposal` and its resulting `RiskAssessment`/`OrderIntent` must
be as auditable as an approved one... Storing only the final decision is not sufficient." This
slice makes a `TradeProposal` durable the moment it exists, independent of anything that later
happens to it.

- `migrations/versions/0011_trade_proposals.py` + `wallybot/infrastructure/models.py`'s
  `TradeProposalRow`: one insert-only table, same "a fresh evaluation is always a new row, never
  updated" pattern as every Phase 10/11 snapshot table (no unique constraint on `proposal_id`
  beyond it being the primary key — a generated ID is never reused, so this is both identity and
  the natural idempotent insert key, not a dedup mechanism against re-analysis). `reasons`,
  `risks`, `supporting_signal_ids`, `invalidating_conditions` and `source_event_ids` persist as
  JSONB, same as `SmartMoneyScoreSnapshotRow.reasons` and friends.
- `wallybot/infrastructure/trade_proposal_repository.py`'s `TradeProposalRepository`:
  **write-only by design.** Reconstructing a full `TradeProposal` back from a row would require
  rebuilding its `Instrument` from stored venue/base/quote identity alone, and this table does not
  persist price/quantity increments or minimum size — the exact same reason `OrderIntentRow` and
  `PriceConsensusResultRow` never reconstruct a full `Instrument` either (see `wallybot.
  infrastructure.unit_of_work`, and Phase 10 Slice 6's own note that "Postgres never stored full
  Instrument fidelity"). Fabricating those fields to make a domain round trip pass would violate
  RISK.md's "do not invent" rule. A future slice that actually needs to read proposals back (an
  admin UI, Phase 14) defines its own read shape against the columns this table really has,
  instead of pretending the original `Instrument` survived.
- `tests/integration/test_trade_proposal_persistence.py` (Testcontainers): verifies persistence by
  querying `TradeProposalRow` directly (not via a domain round trip, per the above) — every field
  lands correctly, and two proposals for the same instrument both persist as independent rows.
- Bumped `apps/api/main.py`'s hardcoded Alembic revision check to `"0011_trade_proposals"` (same
  recurring rough edge every migration since Phase 4 Slice 4 has bumped by hand).

Verified: full suite 438 passed (341→438), ruff/pyright clean, migration applied and verified
against the live `wallybot-api` container (rebuilt, redeployed, head `0011_trade_proposals`,
`/health/ready` → `ready`). Committed.

## Delivered: Slice 3 — SHADOW mode (allocation/risk evaluation, never execution)

Per ARCHITECTURE.md: "SHADOW mode before any LIVE eligibility." `wallybot/application/
shadow_decision_service.py`'s `ShadowDecisionService` runs a `TradeProposal` through the exact
same `PortfolioAllocator.propose`/`RiskEngine.evaluate` gate `DecisionPipeline` uses for
deterministic strategies — translating the proposal into the same `AggregatedSignal` shape
(`contributing_signals` empty, since there's no underlying `StrategySignal`; the proposal's own
`reasons` become `AggregatedSignal.reason`) so both paths run through identical, already-tested
code rather than a second parallel implementation. **The service holds no reference to
`ExecutionService` or an `IdGenerator` at all** — it is structurally incapable of submitting an
order, not merely "chosen" not to. `TradeDirection.SHORT` is refused before allocation, same
reasoning `DecisionPipeline` already applies to SELL (no position data to size a reduction
against).

`wallybot/infrastructure/models.py`'s `ShadowDecisionRow` + `migrations/versions/
0014_shadow_decisions.py` + `wallybot/infrastructure/shadow_decision_repository.py`'s
`ShadowDecisionRepository`: insert-only, **write-only** for the same reason
`TradeProposalRepository` is (no full `Instrument` fidelity persisted to reconstruct a domain
object from). No foreign key to `trade_proposals` — an outcome is recorded whenever this service
runs, independent of whether the proposal itself was persisted.

`tests/unit/test_shadow_decision_service.py`: clean approval, SHORT refused before allocation,
a full bucket rejected at allocation before risk ever runs, and risk rejecting an
allocation-approved proposal. `tests/integration/test_shadow_decision_persistence.py`
(Testcontainers) is this slice's stated acceptance evidence: a SHADOW evaluation persists its
full outcome, and asserts `order_intents` stays empty — the actual proof "never reaches
`ExecutionService.submit`," not just an absence of a call in test code. Bumped
`apps/api/main.py`'s hardcoded Alembic revision check to `"0014_shadow_decisions"`.

**Explicitly not built**: any caller/orchestrator that actually runs `ShadowDecisionService`
against fresh `TradeProposal`s on a schedule (no scheduler wiring exists for this yet, same as
`ReconciliationService.sweep` needing its own future scheduler hookup); any UI surface reading
`shadow_decisions` back; promotion logic from SHADOW to LIVE eligibility (RISK.md's evidence
gates are a human-authorized decision, not something this slice automates).

Verified: full suite 452 passed (447→452), ruff/pyright clean, `shadow_decision_service.py`
imports only `wallybot.domain.*` and stdlib (no execution/persistence dependency, by construction
rather than convention), migration applied and verified against the live `wallybot-api`
container, `/health/ready` → `ready`.
