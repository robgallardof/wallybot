from decimal import Decimal

import pytest

from wallybot.domain.ai_budget import AIBudget, AIUsage, evaluate_ai_budget


def usage(cost: Decimal | None) -> AIUsage:
    return AIUsage("test", "model", 10, 5, cost)


def test_unpriced_usage_is_rejected() -> None:
    result = evaluate_ai_budget(usage(None), Decimal("0"), AIBudget(Decimal("1"), Decimal("2")))
    assert result.allowed is False


def test_budget_rejects_run_and_daily_excesses() -> None:
    budget = AIBudget(Decimal("1"), Decimal("2"))
    assert evaluate_ai_budget(usage(Decimal("1.01")), Decimal("0"), budget).allowed is False
    assert evaluate_ai_budget(usage(Decimal("0.5")), Decimal("1.6"), budget).allowed is False


def test_budget_accepts_cost_at_limits() -> None:
    result = evaluate_ai_budget(
        usage(Decimal("1")), Decimal("1"), AIBudget(Decimal("1"), Decimal("2"))
    )
    assert result.allowed is True


def test_negative_spend_is_invalid() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        evaluate_ai_budget(
            usage(Decimal("0")), Decimal("-0.01"), AIBudget(Decimal("1"), Decimal("2"))
        )
