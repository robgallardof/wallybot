"""The AI analysis loop must be unable to create or submit an order."""

import ast
import inspect

import wallybot.application.ai_decision_loop as ai_decision_loop


def test_analysis_loop_has_no_execution_or_balance_dependencies() -> None:
    source = inspect.getsource(ai_decision_loop)
    tree = ast.parse(source)
    imported = {
        name
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module
            else []
        )
    }
    forbidden = (
        "wallybot.application.execution_service",
        "wallybot.exchanges.fake",
        "wallybot.infrastructure.portfolio_repository",
        "wallybot.domain.order",
    )
    assert not any(name.startswith(forbidden) for name in imported)
    assert "OrderIntent" not in source
    assert "execution.submit" not in source
