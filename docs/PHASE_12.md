# Phase 12 implementation backlog: AI strategy engine and TradeProposal

Status: Slice 1 delivered 2026-09-13. Per ARCHITECTURE.md's implementation sequence: "AI strategy
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

**This session implements Slice 1.**

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
