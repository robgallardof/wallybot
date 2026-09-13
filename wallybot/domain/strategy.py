"""Strategy.evaluate(context) -> StrategySignal: a pure recommendation.

Per ARCHITECTURE.md's Contracts table: "Pure recommendation; cannot submit orders or mutate
balances." A Strategy never touches I/O, never holds credentials, and this module has no method
resembling order submission -- there is nothing here for a strategy to misuse even if it wanted to.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument
from wallybot.domain.regime import RegimeClassification


class Action(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class StrategyContext:
    instrument: Instrument
    features: FeatureVector
    regime: RegimeClassification
    as_of: datetime


@dataclass(frozen=True)
class StrategySignal:
    instrument: Instrument
    strategy_id: str
    version: int
    action: Action
    confidence: Decimal
    as_of: datetime
    reason: str

    def __post_init__(self) -> None:
        if not self.strategy_id:
            raise ValueError("strategy_id is required")
        if self.version < 1:
            raise ValueError("version must be positive")
        if not (Decimal(0) <= self.confidence <= Decimal(1)):
            raise ValueError("confidence must be between 0 and 1")


class Strategy(Protocol):
    def evaluate(self, context: StrategyContext) -> StrategySignal: ...
