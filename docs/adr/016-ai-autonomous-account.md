# ADR-016: Opt-in AI-autonomous PAPER account, deliberately outside the deterministic risk gate

Status: superseded by [ADR-017](017-approved-ai-proposals.md), 2026-09-23. It remains as a
historical record of the rejected direct-execution design and must not be used as implementation
authority.

## Context

ADR-007 ("AI advises; risk decides") and ADR-013 ("a proposal passes `PortfolioAllocator` and
`RiskEngine`") establish that every trading decision, AI-originated or not, is gated by
deterministic risk/allocation controls before it can become an order. The operator explicitly
asked for a new capability that violates this: an AI, invoked through the operator's own local
`claude`/`codex` CLI (not a hosted API), that decides and executes trades without passing through
`PortfolioAllocator`/`DeterministicRiskEngine`/circuit breakers at all.

This was not accepted at face value. The operator was shown concrete failure scenarios before
confirming (hallucinated trades, prompt injection via market data, a single bad tick producing
unbounded loss with no automatic backstop) and was asked twice, including a version of the
question naming the circuit-breaker specifically as the one thing being given up. Both times the
operator confirmed they wanted zero limits on this path, understanding the risk.

## Decision

- A new, fully separate ledger account (`paper-ai:<user_id>`, distinct from `paper:<user_id>`) and
  a new native host process (`apps/ai_worker` — not a Docker container, since it needs the
  operator's own already-authenticated `claude`/`codex` CLI) run an AI-autonomous decision loop
  (`wallybot.application.ai_decision_loop.run_ai_decision_tick`).
- That loop translates a `CliAiProvider`-produced `TradeProposal` directly into an `OrderIntent`
  and submits it through the existing `ExecutionService` — **by construction**, not by a bypassed
  check: the module imports neither `wallybot.domain.risk`, `wallybot.domain.breaker`, nor
  `wallybot.domain.portfolio` (`PortfolioAllocator`). A permanent unit test
  (`tests/unit/test_ai_decision_loop.py`) inspects this module's own imports to keep that
  structural guarantee from silently regressing.
- Gated behind its own toggle (`ai_autonomy_control`, default `DISABLED`), independent of the
  existing `Control.status`/`Control.environment` switch — an operator can pause the deterministic
  loop without touching AI-autonomous trading, and vice versa. Changing it requires
  Admin + fresh MFA, the same bar every other sensitive control in this codebase already uses.
- **What ADR-007/ADR-013 still require, unchanged, for every other path in this codebase**: the
  deterministic strategy (`TrendFollowingStrategy` → `DeterministicRiskEngine` → breakers, via
  `wallybot.application.decision_loop.run_decision_tick`) is not touched by this decision and
  still passes every proposal through risk/allocation exactly as before. This ADR is a narrow,
  named exception for one new, separate, opt-in path — not a repeal of ADR-007/013's general rule.
- **What does not change, for either path**: `apps/ai_worker` still holds no execution/withdrawal
  capability beyond submitting a PAPER order through the existing `ExecutionService`/`FakeExchange`
  simulator. There is still no withdrawal interface, route, background job or research tool
  anywhere in this codebase (SECURITY.md). LIVE trading is unaffected — it remains entirely
  unbuilt (no real order-submission gateway exists at all yet) and gated behind Fase 9's full,
  human-only checklist, independent of this decision.

## Consequences

An AI-originated order on the `paper-ai:` account can lose the entire funded balance of that one
account with no automatic stop — that is the accepted, explicit cost of this decision, confirmed
twice by the operator. It cannot, however: touch the deterministic account's balance, exceed
`apps/ai_worker`'s own least-privilege `wally_ai` DB grants, submit to a real exchange, or
withdraw funds anywhere. Output validation into `TradeProposal`'s existing schema (confidence
range, stop/take-profit ordering, non-empty reasons, staleness check against `signal_ttl`) is
still enforced — that is basic correctness/security hygiene the operator was never asked to
remove, not a risk limit.

**A future session auditing this codebase against ADR-007, ADR-013, `docs/PENDING.md`'s Fase 6
acceptance line ("el veto determinista de riesgo siempre prevalece"), or `AGENTS.md`'s "never let
AI-analyzed output submit trades directly" will find `apps/ai_worker` in apparent violation of all
three. It is not a bug.** Do not add risk/allocator/breaker checks to this path, and do not delete
it, without first re-confirming with the operator — this decision was made deliberately, after two
explicit warnings, and is recorded here for exactly this reason.
