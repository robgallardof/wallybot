"""First concrete PortfolioAllocator: bucket-headroom sizing scaled by signal confidence.

Targets RISK.md's *operating* speculative ceiling only, never the absolute one -- "The 15%
absolute ceiling does not automatically authorize an increase from 10%. Such a change needs
reviewed configuration, fresh MFA and explicit operator action." Nothing in this allocator can
reach the absolute ceiling; that is a deliberately separate, manual path this phase doesn't build.

SELL proposes a *reduction*, never a short: it scales the instrument's own currently-held notional
(`state.asset_exposure[instrument.id]`) by the signal's confidence, so confidence=1 proposes a full
close and it can never propose selling more than is currently held. Bucket/speculative ceilings are
BUY-side concentration limits and do not apply to a reduction.
"""

from datetime import datetime
from decimal import Decimal

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.order import Side
from wallybot.domain.portfolio import (
    AllocationProposal,
    Bucket,
    PortfolioPolicy,
    PortfolioState,
)
from wallybot.domain.strategy import Action

ALLOCATION_VERSION = 1


class SimplePortfolioAllocator:
    """Implements wallybot.domain.portfolio.PortfolioAllocator (structural, not inherited)."""

    def propose(
        self,
        signal: AggregatedSignal,
        bucket: Bucket,
        state: PortfolioState,
        policy: PortfolioPolicy,
        as_of: datetime,
    ) -> AllocationProposal:
        if signal.action == Action.HOLD:
            return self._rejected(signal, bucket, Side.BUY, as_of, "signal is HOLD")
        if signal.action == Action.SELL:
            return self._propose_sell(signal, bucket, state, as_of)

        if state.open_positions >= policy.max_open_positions:
            return self._rejected(signal, bucket, Side.BUY, as_of, "max open positions reached")

        room = self._bucket_room(bucket, state, policy)
        if room <= 0:
            return self._rejected(signal, bucket, Side.BUY, as_of, "bucket ceiling already reached")

        proposed = room * signal.confidence

        if bucket == Bucket.SPECULATIVE:
            proposed = min(proposed, self._speculative_operating_room(state, policy))
            if proposed <= 0:
                reason = "speculative operating ceiling reached"
                return self._rejected(signal, bucket, Side.BUY, as_of, reason)
            proposed = min(proposed, self._single_asset_room(signal, state, policy))
            if proposed <= 0:
                return self._rejected(
                    signal, bucket, Side.BUY, as_of, "single speculative asset ceiling reached"
                )

        if proposed <= 0:
            return self._rejected(signal, bucket, Side.BUY, as_of, "no remaining capacity")

        return AllocationProposal(
            instrument=signal.instrument,
            bucket=bucket,
            side=Side.BUY,
            version=ALLOCATION_VERSION,
            as_of=as_of,
            proposed_notional=proposed,
            approved=True,
            reasons=(),
        )

    def _propose_sell(
        self,
        signal: AggregatedSignal,
        bucket: Bucket,
        state: PortfolioState,
        as_of: datetime,
    ) -> AllocationProposal:
        held = state.asset_exposure.get(signal.instrument.id, Decimal(0))
        if held <= 0:
            return self._rejected(signal, bucket, Side.SELL, as_of, "no open position to reduce")

        proposed = held * signal.confidence
        if proposed <= 0:
            return self._rejected(signal, bucket, Side.SELL, as_of, "no remaining capacity")

        return AllocationProposal(
            instrument=signal.instrument,
            bucket=bucket,
            side=Side.SELL,
            version=ALLOCATION_VERSION,
            as_of=as_of,
            proposed_notional=proposed,
            approved=True,
            reasons=(),
        )

    def _bucket_room(
        self, bucket: Bucket, state: PortfolioState, policy: PortfolioPolicy
    ) -> Decimal:
        target = policy.bucket_targets[bucket] * state.equity
        current = state.bucket_exposure.get(bucket, Decimal(0))
        return target - current

    def _speculative_operating_room(
        self, state: PortfolioState, policy: PortfolioPolicy
    ) -> Decimal:
        cap = policy.speculative_operating_max * state.equity
        current = state.bucket_exposure.get(Bucket.SPECULATIVE, Decimal(0))
        return max(cap - current, Decimal(0))

    def _single_asset_room(
        self, signal: AggregatedSignal, state: PortfolioState, policy: PortfolioPolicy
    ) -> Decimal:
        cap = policy.single_speculative_asset_max * state.equity
        current = state.asset_exposure.get(signal.instrument.id, Decimal(0))
        return max(cap - current, Decimal(0))

    def _rejected(
        self, signal: AggregatedSignal, bucket: Bucket, side: Side, as_of: datetime, reason: str
    ) -> AllocationProposal:
        return AllocationProposal(
            instrument=signal.instrument,
            bucket=bucket,
            side=side,
            version=ALLOCATION_VERSION,
            as_of=as_of,
            proposed_notional=Decimal(0),
            approved=False,
            reasons=(reason,),
        )
