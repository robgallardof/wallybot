"""Deterministic, provider-neutral AI cost guardrails.

An AI adapter reports usage here *after* obtaining a response and before that response becomes
available to downstream services.  This module deliberately has no provider SDK, persistence, or
execution dependency: an over-budget or unpriced response is unusable, never an invitation to
submit a trade.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AIUsage:
    provider: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None

    def __post_init__(self) -> None:
        if not self.provider or not self.model_id:
            raise ValueError("provider and model_id are required")
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("token counts must be nonnegative")
        if self.cost_usd is not None and self.cost_usd < 0:
            raise ValueError("cost_usd must be nonnegative when present")


@dataclass(frozen=True)
class AIBudget:
    max_per_run_usd: Decimal
    max_per_day_usd: Decimal

    def __post_init__(self) -> None:
        if self.max_per_run_usd <= 0 or self.max_per_day_usd <= 0:
            raise ValueError("AI budget limits must be positive")


@dataclass(frozen=True)
class AIBudgetDecision:
    allowed: bool
    reason: str | None


def evaluate_ai_budget(
    usage: AIUsage, already_spent_today_usd: Decimal, budget: AIBudget
) -> AIBudgetDecision:
    """Fail closed when pricing is absent or either immutable limit would be exceeded."""
    if already_spent_today_usd < 0:
        raise ValueError("already_spent_today_usd must be nonnegative")
    if usage.cost_usd is None:
        return AIBudgetDecision(False, "AI usage has no verified cost")
    if usage.cost_usd > budget.max_per_run_usd:
        return AIBudgetDecision(False, "AI per-run budget exceeded")
    if already_spent_today_usd + usage.cost_usd > budget.max_per_day_usd:
        return AIBudgetDecision(False, "AI daily budget exceeded")
    return AIBudgetDecision(True, None)
