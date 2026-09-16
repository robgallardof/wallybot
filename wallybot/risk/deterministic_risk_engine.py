"""First concrete RiskEngine: the deterministic checks RISK.md's Approval contract lists that
this phase can faithfully implement with data already modeled elsewhere in this codebase.

Checks, in order (each an independent, immediately-returning rejection so a caller can always
tell exactly which one fired): the allocator's own approval; mode/authority (control status);
fresh valid data (the quality gate, Slice 3); exchange status; reconciliation health; active
circuit breakers; daily/weekly/drawdown losses ("Equality at a limit triggers the breaker" --
RISK.md, hence >=, not >); spread; bucket/asset capacity (re-derived authoritatively -- this
engine is the final word, not a rubber stamp on the allocator's proposal, and may reduce size
here); instrument precision and minimum quantity (also may reduce size). A reduction at any of
the last two steps yields APPROVED_WITH_REDUCED_SIZE, never a silent full rejection, unless the
reduced amount is not directly tradable -- "Zero-sized approvals are rejected."
"""

from datetime import datetime
from decimal import ROUND_DOWN, Decimal

from wallybot.domain.control import Status
from wallybot.domain.market import Instrument
from wallybot.domain.portfolio import AllocationProposal, Bucket
from wallybot.domain.quality import QualityStatus
from wallybot.domain.risk import (
    ExchangeStatus,
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskPolicy,
)

RISK_ASSESSMENT_VERSION = 1


class DeterministicRiskEngine:
    """Implements wallybot.domain.risk.RiskEngine (structural, not inherited)."""

    def evaluate(
        self, proposal: AllocationProposal, context: RiskContext, policy: RiskPolicy
    ) -> RiskAssessment:
        as_of = context.as_of
        expires_at = as_of + context.expiry

        blocking = self._first_blocking_reason(proposal, context, policy)
        if blocking is not None:
            return self._rejected(as_of, expires_at, blocking)

        available = self._authoritative_capacity(proposal, context)
        if available <= 0:
            return self._rejected(
                as_of, expires_at, "no remaining bucket/asset capacity at risk evaluation time"
            )

        reasons: list[str] = []
        final_notional = proposal.proposed_notional
        if available < final_notional:
            reasons.append(f"reduced from {final_notional} to {available}: capacity limit")
            final_notional = available

        final_notional, final_quantity, quantity_reason = self._apply_instrument_precision(
            final_notional, proposal.instrument, context
        )
        if quantity_reason is not None:
            reasons.append(quantity_reason)

        if final_notional <= 0:
            return self._rejected(as_of, expires_at, "quantity rounds below instrument minimum")

        decision = RiskDecision.APPROVED_WITH_REDUCED_SIZE if reasons else RiskDecision.APPROVED
        if not reasons:
            reasons.append("approved: within all evaluated limits")

        return RiskAssessment(
            decision=decision,
            final_notional=final_notional,
            final_quantity=final_quantity,
            version=RISK_ASSESSMENT_VERSION,
            as_of=as_of,
            expires_at=expires_at,
            reasons=tuple(reasons),
        )

    def _first_blocking_reason(
        self, proposal: AllocationProposal, context: RiskContext, policy: RiskPolicy
    ) -> str | None:
        if not proposal.approved:
            return "proposal was not approved by the allocator"
        if context.control_status != Status.RUNNING:
            return f"control status is {context.control_status}, not RUNNING"
        if context.quality.status == QualityStatus.FAILURE:
            return "market data quality check failed"
        if context.exchange_status != ExchangeStatus.HEALTHY:
            return f"exchange status is {context.exchange_status}"
        if not context.reconciliation_healthy:
            return "reconciliation is not healthy"
        if context.active_breakers:
            return f"active breaker(s): {', '.join(sorted(context.active_breakers))}"
        if context.daily_loss >= policy.max_daily_loss:
            return f"daily loss {context.daily_loss} at or beyond limit {policy.max_daily_loss}"
        if context.weekly_loss >= policy.max_weekly_loss:
            return f"weekly loss {context.weekly_loss} at or beyond limit {policy.max_weekly_loss}"
        if context.drawdown >= policy.max_drawdown:
            return f"drawdown {context.drawdown} at or beyond limit {policy.max_drawdown}"
        if context.snapshot.spread_ratio > policy.max_spread_ratio:
            return f"spread {context.snapshot.spread_ratio} exceeds limit {policy.max_spread_ratio}"
        return None

    def _authoritative_capacity(
        self, proposal: AllocationProposal, context: RiskContext
    ) -> Decimal:
        state, config = context.portfolio_state, context.portfolio_policy
        target = config.bucket_targets[proposal.bucket] * state.equity
        available = target - state.bucket_exposure.get(proposal.bucket, Decimal(0))
        if proposal.bucket == Bucket.SPECULATIVE:
            operating_cap = config.speculative_operating_max * state.equity
            operating_room = operating_cap - state.bucket_exposure.get(
                Bucket.SPECULATIVE, Decimal(0)
            )
            asset_cap = config.single_speculative_asset_max * state.equity
            asset_room = asset_cap - state.asset_exposure.get(proposal.instrument.id, Decimal(0))
            available = min(available, operating_room, asset_room)
        return max(available, Decimal(0))

    def _apply_instrument_precision(
        self, notional: Decimal, instrument: Instrument, context: RiskContext
    ) -> tuple[Decimal, Decimal, str | None]:
        # Instrument.quantity_increment/min_quantity are optional at the domain level (some
        # providers, e.g. Tiingo, don't report them) -- but real order sizing can never proceed
        # without them, so this fails closed and loudly rather than guessing a step size.
        if instrument.quantity_increment is None or instrument.min_quantity is None:
            raise ValueError(
                f"{instrument.id} has no reported precision; cannot size an order against it"
            )
        mid_price = (context.snapshot.bid + context.snapshot.ask) / 2
        raw_quantity = notional / mid_price
        quantity = raw_quantity.quantize(instrument.quantity_increment, rounding=ROUND_DOWN)
        if quantity < instrument.min_quantity:
            return Decimal(0), Decimal(0), None
        rounded_notional = quantity * mid_price
        if rounded_notional < notional:
            reason = f"quantity rounded down to instrument step ({quantity})"
            return rounded_notional, quantity, reason
        return rounded_notional, quantity, None

    def _rejected(self, as_of: datetime, expires_at: datetime, reason: str) -> RiskAssessment:
        return RiskAssessment(
            decision=RiskDecision.REJECTED,
            final_notional=Decimal(0),
            final_quantity=Decimal(0),
            version=RISK_ASSESSMENT_VERSION,
            as_of=as_of,
            expires_at=expires_at,
            reasons=(reason,),
        )
