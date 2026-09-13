"""RiskEngine.evaluate(proposal, context) -> RiskAssessment: the authoritative approval gate.

Per ARCHITECTURE.md's Contracts table and RISK.md's Approval contract: "Risk receives an
immutable proposed intent plus account equity, positions, reservations, fresh market data,
regime, quality result, exchange status, reconciliation status and protected policy version.
Output is APPROVED, REJECTED or APPROVED_WITH_REDUCED_SIZE, with final quantity, reason codes,
input hashes/versions and expiry. Zero-sized approvals are rejected."

RiskEngine computes nothing beyond what RiskContext hands it -- equity history, reconciliation
and breaker *state* are infrastructure this phase does not build (Phase 4 ledger/execution); this
port only makes the deterministic approval decision from data already gathered elsewhere.

Deliberately out of scope for the initial policy modeled here: volatility/correlation limits
(nothing in this codebase computes volatility yet -- only momentum, per Phase 3 Slice 8) and any
AI-related check (there is no AI provider built; Phase 6). RISK.md is explicit that limits with no
safe universal default (spread, liquidity, slippage, quote age...) must be configured per
venue/instrument and fail closed if missing -- RiskPolicy has no optional/defaulted fields for
those; every field is required at construction.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.control import Status
from wallybot.domain.market import MarketSnapshot
from wallybot.domain.portfolio import AllocationProposal, PortfolioPolicy, PortfolioState
from wallybot.domain.quality import QualityReport


class RiskDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVED_WITH_REDUCED_SIZE = "APPROVED_WITH_REDUCED_SIZE"


class ExchangeStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class RiskPolicy:
    """RISK.md's Initial Policy table, verbatim -- version, loss/drawdown limits and spread are
    all required, never optional-with-a-guessed-default."""

    version: int
    max_daily_loss: Decimal
    max_weekly_loss: Decimal
    max_drawdown: Decimal
    max_spread_ratio: Decimal

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        for name, value in (
            ("max_daily_loss", self.max_daily_loss),
            ("max_weekly_loss", self.max_weekly_loss),
            ("max_drawdown", self.max_drawdown),
            ("max_spread_ratio", self.max_spread_ratio),
        ):
            if not (Decimal(0) < value <= Decimal(1)):
                raise ValueError(f"{name} must be between 0 (exclusive) and 1")


@dataclass(frozen=True)
class RiskContext:
    control_status: Status
    portfolio_state: PortfolioState
    portfolio_policy: PortfolioPolicy
    quality: QualityReport
    snapshot: MarketSnapshot
    exchange_status: ExchangeStatus
    reconciliation_healthy: bool
    active_breakers: frozenset[str]
    daily_loss: Decimal
    weekly_loss: Decimal
    drawdown: Decimal
    as_of: datetime
    expiry: timedelta

    def __post_init__(self) -> None:
        if self.expiry <= timedelta(0):
            raise ValueError("expiry must be positive")
        for name, value in (
            ("daily_loss", self.daily_loss),
            ("weekly_loss", self.weekly_loss),
            ("drawdown", self.drawdown),
        ):
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")


@dataclass(frozen=True)
class RiskAssessment:
    decision: RiskDecision
    final_notional: Decimal
    final_quantity: Decimal
    version: int
    as_of: datetime
    expires_at: datetime
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.expires_at <= self.as_of:
            raise ValueError("expires_at must be after as_of")
        if self.decision == RiskDecision.REJECTED:
            if self.final_notional != 0:
                raise ValueError("a REJECTED assessment must have zero final_notional")
            if self.final_quantity != 0:
                raise ValueError("a REJECTED assessment must have zero final_quantity")
        else:
            if self.final_notional <= 0:
                raise ValueError("an approved assessment must have a positive final_notional")
            if self.final_quantity <= 0:
                raise ValueError("an approved assessment must have a positive final_quantity")
        if not self.reasons:
            raise ValueError("reasons must not be empty -- every decision needs evidence")


class RiskEngine(Protocol):
    def evaluate(
        self, proposal: AllocationProposal, context: RiskContext, policy: RiskPolicy
    ) -> RiskAssessment: ...
