"""First deterministic strategy: pure trend-following off regime + momentum.

No execution capability -- returns a StrategySignal recommendation only. DRAFT status per
RISK.md's promotion ladder (DRAFT -> BACKTESTED -> VALIDATED -> PAPER -> CANDIDATE -> LIVE);
nothing here promotes it further.
"""

from decimal import Decimal

from wallybot.domain.regime import Regime
from wallybot.domain.strategy import Action, StrategyContext, StrategySignal

STRATEGY_ID = "trend_following"
STRATEGY_VERSION = 1

_ACTION_BY_REGIME = {
    Regime.TRENDING_UP: Action.BUY,
    Regime.TRENDING_DOWN: Action.SELL,
    Regime.RANGING: Action.HOLD,
    Regime.RISK_OFF: Action.HOLD,
}


class TrendFollowingStrategy:
    """Implements wallybot.domain.strategy.Strategy (structural, not inherited)."""

    def evaluate(self, context: StrategyContext) -> StrategySignal:
        if context.regime.instrument != context.instrument:
            raise ValueError("regime classification is for a different instrument")
        if context.features.instrument != context.instrument:
            raise ValueError("feature vector is for a different instrument")

        momentum_key = next(
            (key for key in context.features.values if key.startswith("momentum_")), None
        )
        if momentum_key is None:
            raise ValueError("feature vector must include a momentum_<window> value")
        momentum = context.features.values[momentum_key]

        action = _ACTION_BY_REGIME[context.regime.regime]
        confidence = min(abs(momentum), Decimal("1"))
        reason = f"regime={context.regime.regime}, {momentum_key}={momentum}"

        return StrategySignal(
            instrument=context.instrument,
            strategy_id=STRATEGY_ID,
            version=STRATEGY_VERSION,
            action=action,
            confidence=confidence,
            as_of=context.as_of,
            reason=reason,
        )
