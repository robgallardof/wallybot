# AI: contracts exist, no provider is connected

Status: this is genuinely a stub in the sense that matters most — **no real AI model is ever
called**. There is no OpenAI adapter, no Anthropic adapter, no API route, and no UI for anything
AI-related. What does exist is a set of real, tested domain contracts (`AIProvider`,
`TradeProposal`, cost budget guardrails, a SHADOW-mode evaluation path, and write-only persistence)
that a future provider adapter would plug into. `docs/PENDING.md`'s Fase 6 ("IA opcional,
calibración y costes") is entirely unchecked, and `.ai/CURRENT.md` records it plainly: "Fase 6 AI
provider is still a fake-only stub" — this document does not contradict that, it only describes
exactly what "stub" means here in code terms.

## What exists

**`AIProvider.analyze(context) -> TradeProposal | None`** (`wallybot/domain/trade_proposal.py`) is
the port ARCHITECTURE.md's Contracts table names. It is pure domain: no framework imports, no I/O.
`TradeProposal` is a fully validated dataclass carrying every field ARCHITECTURE.md's "AI strategy
layer and TradeProposal" section specifies — instrument, direction, strategy, confidence, suggested
allocation/entry/stop/take-profit, time horizon, signal TTL, reasons, risks, supporting signal IDs,
invalidating conditions, source event IDs, model ID and prompt version — with real `__post_init__`
validation (stop must be on the correct side of entry for the direction, confidence in `[0, 1]`,
`reasons` must be non-empty "since every proposal needs evidence"). Returning `None` — never a
fabricated placeholder — is the contract for "no actionable idea" or "output failed schema
validation," matching RISK.md's requirement that AI-required strategies HOLD when AI is
unavailable.

**`FakeAIProvider`** (`wallybot/intelligence/fake_ai.py`) is a seeded, network-free implementation
for tests only — it returns exactly one scripted `TradeProposal` per instrument, or `None` for
anything not seeded. Its own docstring is explicit: "No real model call, no API key, no
plausible-random generator: no real AIProvider adapter is integrated yet to give a generator
something to imitate."

**`AIBudget`/`AIUsage`/`evaluate_ai_budget`** (`wallybot/domain/ai_budget.py`) are real, tested,
provider-neutral cost guardrails: per-run and per-day USD ceilings, failing closed on any usage
with no verified cost (`cost_usd=None` is rejected, never treated as free). This module has no
provider SDK or persistence dependency — it is ready to be called by a future adapter, but nothing
calls it today; there is no accumulation of "already spent today" anywhere in the running system.

**`ShadowDecisionService`** (`wallybot/application/shadow_decision_service.py`) runs a
`TradeProposal` through the same `PortfolioAllocator.propose`/`RiskEngine.evaluate` gate
`DecisionPipeline` uses, translating it into the same `AggregatedSignal` shape a `SignalAggregator`
would have produced. It structurally cannot submit an order — it holds no reference to
`ExecutionService` or an `IdGenerator`, "not merely 'chosen' not to," per its own docstring. This
implements the SHADOW mode ARCHITECTURE.md's implementation sequence calls for ("AI strategy engine
... SHADOW mode before any LIVE eligibility"), but nothing in `apps/` ever calls
`ShadowDecisionService` — there is no scheduled job, no route, and no caller anywhere outside its
own test suite.

**`TradeProposalRepository`** (`wallybot/infrastructure/trade_proposal_repository.py`) is a real,
insert-only audit table for `TradeProposal` — but it is deliberately write-only (it does not
reconstruct a full `Instrument` from stored columns, the same "never fabricate a precision field"
rule `historical_query.py` documents) and, more importantly, nothing in `apps/api` ever calls
`save()`. There is no `TradeProposal` ever created by a running process today, so this table stays
empty in production.

## What does not exist

- **No provider adapter.** No OpenAI client, no Anthropic client, no HTTP call to any AI service
  anywhere in `wallybot/` or `apps/`. `ARCHITECTURE.md`'s Fase 6 bullet ("Implementar puerto
  AIProvider y adaptadores OpenAI/Anthropic con esquemas estrictos, límites y trazabilidad") is
  unstarted beyond the port itself.
- **No API routes.** There is no `ai_routes.py`, no `/api/ai/*` endpoint, and no route that reads
  or writes a `TradeProposal`.
- **No UI.** No AI decisions page, no cost/budget dashboard — `docs/PENDING.md` Fase 6's "Entregar
  UI de decisiones IA y contabilidad de costes" is unchecked, and there is nothing in `apps/web` to
  check against.
- **No wiring into the live loop.** `DecisionPipeline`/`run_decision_tick` (see
  [TRADING.md](TRADING.md)) never constructs an `AIAnalysisContext` or calls `AIProvider.analyze`.
  AI plays no role in any order this codebase has ever placed.
- **No routing, timeout, fallback or per-execution/day budget enforcement in a live path.** The
  domain pieces for budget enforcement exist (`ai_budget.py`) but are not connected to anything
  that spends money.
- **No calibration, no with/without-AI comparison, no consensus.** `docs/PENDING.md` Fase 6's
  remaining bullets (validate output/symbols/expiry as untrusted data end-to-end, calibration and
  posterior comparison) have no implementation beyond `TradeProposal`'s own field-level validation.

## What would need to happen before this is real

Per `docs/PENDING.md`'s own framing (echoed in `.ai/CURRENT.md`: "Blocked on external decisions:
Fase 6 AI (model/API key)"), the next step here is a provider/model decision and an API key, then
an adapter that turns raw model output into a schema-validated `TradeProposal` (or `None` on
failure) — implementing `AIProvider` behind an HTTP client the same way `wallybot/exchanges/
kraken.py` implements `MarketDataProvider` behind one. Everything downstream of that call already
exists and is tested (`ShadowDecisionService`, `AIBudget`, `TradeProposalRepository`); what is
missing is the one component that would make any of it reachable from a real request.

See [ARCHITECTURE.md](../ARCHITECTURE.md)'s "AI strategy layer and TradeProposal" section for the
target pipeline, and [SECURITY.md](../SECURITY.md)'s "Secret and agent isolation" section for the
constraints any future provider adapter and its tool surface must respect (no execution capability,
no secret access beyond its own API key, provider output always treated as untrusted data).
