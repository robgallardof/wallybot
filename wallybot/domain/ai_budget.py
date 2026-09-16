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
    """Reported cost of one AI provider call, after the fact.

    :ivar provider: Provider identifier, e.g. ``"anthropic"``.
    :ivar model_id: Model identifier as billed by the provider.
    :ivar input_tokens: Prompt tokens consumed; must be nonnegative.
    :ivar output_tokens: Completion tokens consumed; must be nonnegative.
    :ivar cost_usd: Verified cost in USD, or ``None`` if the provider gave no pricing -- treated
        as unusable by :func:`evaluate_ai_budget`, never assumed free.
    :raises ValueError: If ``provider``/``model_id`` is empty, a token count is negative, or
        ``cost_usd`` is negative.
    """

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
    """Immutable per-run and per-day USD ceilings for AI spend.

    :ivar max_per_run_usd: Maximum cost a single call may incur; must be positive.
    :ivar max_per_day_usd: Maximum cumulative cost per day; must be positive.
    :raises ValueError: If either limit is not positive.
    """

    max_per_run_usd: Decimal
    max_per_day_usd: Decimal

    def __post_init__(self) -> None:
        if self.max_per_run_usd <= 0 or self.max_per_day_usd <= 0:
            raise ValueError("AI budget limits must be positive")


@dataclass(frozen=True)
class AIBudgetDecision:
    """Result of :func:`evaluate_ai_budget`.

    :ivar allowed: Whether the usage may be accepted.
    :ivar reason: ``None`` when allowed; otherwise a short, user-facing explanation.
    """

    allowed: bool
    reason: str | None


def evaluate_ai_budget(
    usage: AIUsage, already_spent_today_usd: Decimal, budget: AIBudget
) -> AIBudgetDecision:
    """Decide whether an AI usage's cost may be accepted, failing closed on any uncertainty.

    Rejects usage with no verified cost, usage exceeding the per-run limit on its own, or usage
    that would push the day's cumulative spend over the daily limit. Never partially allows a
    call -- it is accepted in full or rejected in full.

    :param usage: The usage being evaluated; see :class:`AIUsage`.
    :param already_spent_today_usd: Verified USD spent so far today, before this usage.
    :param budget: The immutable limits to check against; see :class:`AIBudget`.
    :returns: :class:`AIBudgetDecision` with ``allowed`` and, if rejected, a ``reason``.
    :raises ValueError: If ``already_spent_today_usd`` is negative.
    """
    if already_spent_today_usd < 0:
        raise ValueError("already_spent_today_usd must be nonnegative")
    if usage.cost_usd is None:
        return AIBudgetDecision(False, "AI usage has no verified cost")
    if usage.cost_usd > budget.max_per_run_usd:
        return AIBudgetDecision(False, "AI per-run budget exceeded")
    if already_spent_today_usd + usage.cost_usd > budget.max_per_day_usd:
        return AIBudgetDecision(False, "AI daily budget exceeded")
    return AIBudgetDecision(True, None)
