"""AIProvider.analyze(context) -> TradeProposal: the AI's only output artifact.

Per ARCHITECTURE.md's "AI strategy layer and TradeProposal": "an AI model is an analyst and
strategy generator, never an executor. Its only output is a schema-validated TradeProposal
(asset, market, direction, strategy, confidence, suggested allocation/entry/stop/take-profit,
time horizon, signal TTL, reasons, risks, supporting signals, invalidating conditions, source
event IDs, model ID and prompt version) ... Invalid or malformed model output fails closed: it
cannot become an executable recommendation, and AI-required strategies HOLD when AI is
unavailable, exactly as RISK.md already requires."

This module is pure domain: no framework imports, no I/O, no execution capability anywhere in its
surface -- parsing/validating raw model output into a TradeProposal is an infrastructure
adapter's job (a later slice), the same split `wallybot/exchanges/kraken.py` already keeps from
this package. Nothing here can submit an order, mutate a balance, or change risk policy.

Deliberately out of scope here (see docs/PHASE_12.md for the full slice plan): persistence, any
wiring into RiskEngine/PortfolioAllocator/ExecutionService/DecisionPipeline, SHADOW mode, the
typed read-only AI tool surface ARCHITECTURE.md names, and any cost/budget accounting (Phase 6
was never built).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument
from wallybot.domain.regime import RegimeClassification
from wallybot.domain.strategy import StrategySignal
from wallybot.domain.validation import require_aware_datetime, require_unit_interval


class TradeDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class AIAnalysisContext:
    """What the AI reasons from -- deliberately the same validated inputs `Strategy.evaluate`
    already consumes (features, regime), plus whatever deterministic strategies already
    concluded for this instrument, not a second, unvetted data path."""

    instrument: Instrument
    features: FeatureVector
    regime: RegimeClassification
    strategy_signals: tuple[StrategySignal, ...]
    as_of: datetime

    def __post_init__(self) -> None:
        require_aware_datetime(self.as_of, "as_of")


@dataclass(frozen=True)
class TradeProposal:
    """Every field ARCHITECTURE.md's Contracts table names for `AIProvider.analyze`, verbatim:
    asset/market (`instrument`), direction, strategy, confidence, suggested allocation/entry/
    stop/take-profit, time horizon, signal TTL, reasons, risks, supporting signals, invalidating
    conditions, source event IDs, model ID and prompt version."""

    proposal_id: str
    instrument: Instrument
    direction: TradeDirection
    strategy_id: str
    confidence: Decimal
    suggested_allocation_pct: Decimal
    entry_price: Decimal
    stop_price: Decimal | None
    take_profit_price: Decimal | None
    time_horizon: timedelta
    signal_ttl: timedelta
    reasons: tuple[str, ...]
    risks: tuple[str, ...]
    supporting_signal_ids: tuple[str, ...]
    invalidating_conditions: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    model_id: str
    prompt_version: str
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError("proposal_id is required")
        if not self.strategy_id:
            raise ValueError("strategy_id is required")
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.prompt_version:
            raise ValueError("prompt_version is required")
        require_aware_datetime(self.as_of, "as_of")
        require_unit_interval(self.confidence, "confidence")
        if not (Decimal(0) < self.suggested_allocation_pct <= Decimal(1)):
            raise ValueError("suggested_allocation_pct must be between 0 (exclusive) and 1")
        if self.entry_price <= 0:
            raise ValueError("entry_price must be positive")
        if self.stop_price is not None and self.stop_price <= 0:
            raise ValueError("stop_price must be positive when present")
        if self.take_profit_price is not None and self.take_profit_price <= 0:
            raise ValueError("take_profit_price must be positive when present")
        if self.direction == TradeDirection.LONG:
            if self.stop_price is not None and self.stop_price >= self.entry_price:
                raise ValueError("a LONG stop_price must be below entry_price")
            if self.take_profit_price is not None and self.take_profit_price <= self.entry_price:
                raise ValueError("a LONG take_profit_price must be above entry_price")
        else:
            if self.stop_price is not None and self.stop_price <= self.entry_price:
                raise ValueError("a SHORT stop_price must be above entry_price")
            if self.take_profit_price is not None and self.take_profit_price >= self.entry_price:
                raise ValueError("a SHORT take_profit_price must be below entry_price")
        if self.time_horizon <= timedelta(0):
            raise ValueError("time_horizon must be positive")
        if self.signal_ttl <= timedelta(0):
            raise ValueError("signal_ttl must be positive")
        if not self.reasons:
            raise ValueError("reasons must not be empty -- every proposal needs evidence")


class AIProvider(Protocol):
    """Per ARCHITECTURE.md's Contracts table: `AIProvider.analyze(context) -> TradeProposal`.
    Async, like every other provider port that calls an external service
    (`WalletIntelligenceProvider`, `SecurityAnalysisProvider`) -- unlike a pure `Strategy`, a real
    AIProvider makes a network call.

    Returns `None` -- never a fabricated placeholder -- when the model has no actionable idea or
    its raw output fails schema validation. Callers must treat `None` as HOLD, exactly as
    RISK.md requires for AI-required strategies when AI is unavailable. No method on this
    Protocol can submit an order, withdraw, transfer funds, change risk policy, or read a private
    key/exchange secret -- SECURITY.md's "Secret and agent isolation" boundary.
    """

    async def analyze(self, context: AIAnalysisContext) -> TradeProposal | None: ...
