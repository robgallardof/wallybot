"""First concrete SignalAggregator: fixed, versioned strategy weights.

Confidence-weighted votes for BUY vs SELL are compared against total participating weight; HOLD
is returned both when quorum isn't met and when the weighted agreement is too thin to act on --
a strategy conflict is not treated as a coin flip, it is treated as "no signal."
"""

from datetime import datetime
from decimal import Decimal

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.market import Instrument
from wallybot.domain.strategy import Action, StrategySignal

AGGREGATION_VERSION = 1


class WeightedSignalAggregator:
    """Implements wallybot.domain.aggregation.SignalAggregator (structural, not inherited)."""

    def __init__(
        self,
        weights: dict[str, Decimal],
        min_quorum: int,
        min_agreement_ratio: Decimal,
    ) -> None:
        if min_quorum < 1:
            raise ValueError("min_quorum must be positive")
        if not (Decimal(0) < min_agreement_ratio <= Decimal(1)):
            raise ValueError("min_agreement_ratio must be between 0 (exclusive) and 1")
        for strategy_id, weight in weights.items():
            if weight <= 0:
                raise ValueError(f"weight for '{strategy_id}' must be positive")
        self.weights = weights
        self.min_quorum = min_quorum
        self.min_agreement_ratio = min_agreement_ratio

    def aggregate(self, signals: list[StrategySignal], as_of: datetime) -> AggregatedSignal:
        if not signals:
            raise ValueError("signals must not be empty")
        instrument = signals[0].instrument
        for signal in signals:
            if signal.instrument != instrument:
                raise ValueError("all signals must be for the same instrument")
            if signal.strategy_id not in self.weights:
                raise ValueError(f"no configured weight for strategy '{signal.strategy_id}'")

        if len(signals) < self.min_quorum:
            return self._hold(
                instrument, signals, as_of, f"quorum not met: {len(signals)} < {self.min_quorum}"
            )

        total_weight = sum((self.weights[s.strategy_id] for s in signals), Decimal(0))
        buy_weight = sum(
            (self.weights[s.strategy_id] * s.confidence for s in signals if s.action == Action.BUY),
            Decimal(0),
        )
        sell_weight = sum(
            (
                self.weights[s.strategy_id] * s.confidence
                for s in signals
                if s.action == Action.SELL
            ),
            Decimal(0),
        )
        net = buy_weight - sell_weight
        agreement_ratio = abs(net) / total_weight if total_weight > 0 else Decimal(0)

        if agreement_ratio < self.min_agreement_ratio:
            reason = f"agreement {agreement_ratio} below minimum {self.min_agreement_ratio}"
            return self._hold(instrument, signals, as_of, reason)

        action = Action.BUY if net > 0 else Action.SELL if net < 0 else Action.HOLD
        return AggregatedSignal(
            instrument=instrument,
            action=action,
            confidence=min(agreement_ratio, Decimal(1)),
            version=AGGREGATION_VERSION,
            as_of=as_of,
            contributing_signals=tuple(signals),
            reason=f"net={net}, agreement={agreement_ratio}",
        )

    def _hold(
        self,
        instrument: Instrument,
        signals: list[StrategySignal],
        as_of: datetime,
        reason: str,
    ) -> AggregatedSignal:
        return AggregatedSignal(
            instrument=instrument,
            action=Action.HOLD,
            confidence=Decimal(0),
            version=AGGREGATION_VERSION,
            as_of=as_of,
            contributing_signals=tuple(signals),
            reason=reason,
        )
