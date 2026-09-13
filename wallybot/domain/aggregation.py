"""SignalAggregator: deterministic weighting, agreement and disagreement, HOLD on invalid
quorum -- per ARCHITECTURE.md's Contracts table. One strategy's opinion is not consensus; this
is the first thing that treats multiple StrategySignals as a single decision.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from wallybot.domain.market import Instrument
from wallybot.domain.strategy import Action, StrategySignal


@dataclass(frozen=True)
class AggregatedSignal:
    instrument: Instrument
    action: Action
    confidence: Decimal
    version: int
    as_of: datetime
    contributing_signals: tuple[StrategySignal, ...]
    reason: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if not (Decimal(0) <= self.confidence <= Decimal(1)):
            raise ValueError("confidence must be between 0 and 1")


class SignalAggregator(Protocol):
    def aggregate(self, signals: list[StrategySignal], as_of: datetime) -> AggregatedSignal: ...
