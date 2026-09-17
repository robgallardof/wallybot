"""PortfolioAllocator: proposed allocation under bucket, asset and cluster capacities.

Per ARCHITECTURE.md's Contracts table. This is a *proposal*, not the authoritative approval --
RiskEngine (Phase 3 Slice 5, deliberately not built here) has final say and does the real
stop-risk position-sizing math from RISK.md's "Loss calculations and sizing" section (entry/stop
price, risk budget -- concepts this phase has no representation for yet). This allocator only
answers "how much bucket/asset headroom exists," using RISK.md's own given initial policy numbers
-- it invents no thresholds of its own.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.market import Instrument
from wallybot.domain.order import Side


class Bucket(StrEnum):
    CORE = "CORE"
    GROWTH = "GROWTH"
    SPECULATIVE = "SPECULATIVE"


@dataclass(frozen=True)
class PortfolioPolicy:
    """Defaults come from RISK.md's Initial policy table -- not invented here."""

    version: int
    bucket_targets: Mapping[Bucket, Decimal]
    speculative_operating_max: Decimal
    speculative_absolute_max: Decimal
    single_speculative_asset_max: Decimal
    max_open_positions: int

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if set(self.bucket_targets) != set(Bucket):
            raise ValueError("bucket_targets must cover every Bucket exactly once")
        for bucket, target in self.bucket_targets.items():
            if not (Decimal(0) < target <= Decimal(1)):
                raise ValueError(f"bucket target for {bucket} must be between 0 and 1")
        if sum(self.bucket_targets.values()) != Decimal(1):
            raise ValueError("bucket_targets must sum to exactly 1")
        if not (Decimal(0) < self.speculative_operating_max <= self.speculative_absolute_max):
            raise ValueError("speculative_operating_max must be positive and <= absolute max")
        if self.speculative_absolute_max > Decimal(1):
            raise ValueError("speculative_absolute_max cannot exceed 1")
        if not (Decimal(0) < self.single_speculative_asset_max <= self.speculative_operating_max):
            raise ValueError("single_speculative_asset_max must be positive and <= operating max")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be positive")


@dataclass(frozen=True)
class PortfolioState:
    """Grouped across venues for concentration, per RISK.md ("Group assets across venues")."""

    equity: Decimal
    bucket_exposure: Mapping[Bucket, Decimal]
    asset_exposure: Mapping[str, Decimal]
    open_positions: int

    def __post_init__(self) -> None:
        if self.equity <= 0:
            raise ValueError("equity must be positive")
        for bucket, exposure in self.bucket_exposure.items():
            if exposure < 0:
                raise ValueError(f"bucket exposure for {bucket} must be nonnegative")
        for instrument_id, exposure in self.asset_exposure.items():
            if exposure < 0:
                raise ValueError(f"asset exposure for {instrument_id} must be nonnegative")
        if self.open_positions < 0:
            raise ValueError("open_positions must be nonnegative")


@dataclass(frozen=True)
class AllocationProposal:
    instrument: Instrument
    bucket: Bucket
    side: Side
    version: int
    as_of: datetime
    proposed_notional: Decimal
    approved: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.proposed_notional < 0:
            raise ValueError("proposed_notional must be nonnegative")
        if self.approved and self.proposed_notional <= 0:
            raise ValueError("an approved proposal must have a positive notional")
        if not self.approved and self.proposed_notional != 0:
            raise ValueError("a rejected proposal must have zero notional")


class PortfolioAllocator(Protocol):
    def propose(
        self,
        signal: AggregatedSignal,
        bucket: Bucket,
        state: PortfolioState,
        policy: PortfolioPolicy,
        as_of: datetime,
    ) -> AllocationProposal: ...
