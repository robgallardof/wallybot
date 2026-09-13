"""Provider reliability tracking, per ARCHITECTURE.md: "Provider reliability (latency, errors,
rate limits, freshness, outages, cross-provider disagreement) drives circuit breakers and
exponential backoff with jitter; no single provider is ever the sole source of truth for a
decision that can move money."

This slice computes a reliability snapshot from a rolling window of raw call outcomes. It does
*not* itself implement a circuit breaker or backoff policy -- wiring a computed
`ProviderReliabilityStatus` into the existing breaker mechanism in `wallybot/risk/` is real future
work, not implied by this slice. Rate-limit pressure, outage detection and cross-provider
disagreement all need signals no current adapter surfaces yet (`KrakenExchange`/
`CoinGeckoMarketMetadataProvider` don't report rate-limit headers, and there is only ever one
provider per data kind wired up so far, so there is nothing to disagree across) --
`UNEVALUATED_DIMENSIONS` names them explicitly rather than guessing.

Pure domain: no framework imports, no HTTP client.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.validation import require_aware_datetime

MIN_CALLS_FOR_STATUS = 5

UNEVALUATED_DIMENSIONS = (
    "rate_limit_pressure",
    "outage_detection",
    "cross_provider_disagreement",
)

_DEGRADED_ERROR_RATE = Decimal("0.1")
_UNRELIABLE_ERROR_RATE = Decimal("0.5")
_DEGRADED_LATENCY_MS = Decimal("2000")
_UNRELIABLE_LATENCY_MS = Decimal("5000")


class ProviderReliabilityStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNRELIABLE = "UNRELIABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ProviderCallOutcome:
    """One observed call to a provider -- the raw material a reliability snapshot is computed
    from. `latency_ms` is always required: even a failed call has a measurable time-to-failure."""

    provider: str
    succeeded: bool
    latency_ms: Decimal
    occurred_at: datetime

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        require_aware_datetime(self.occurred_at, "occurred_at")


@dataclass(frozen=True)
class ProviderReliabilitySnapshot:
    provider: str
    status: ProviderReliabilityStatus
    call_count: int
    error_rate: Decimal | None
    average_latency_ms: Decimal | None
    seconds_since_last_success: Decimal | None
    computed_at: datetime
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider:
            raise ValueError("provider is required")
        if self.call_count < 0:
            raise ValueError("call_count cannot be negative")
        if self.status is ProviderReliabilityStatus.INSUFFICIENT_DATA:
            if self.error_rate is not None or self.average_latency_ms is not None:
                raise ValueError("an INSUFFICIENT_DATA snapshot must not carry computed metrics")
        else:
            if self.error_rate is None or self.average_latency_ms is None:
                raise ValueError("a computed status must carry error_rate and average_latency_ms")
            if not (Decimal(0) <= self.error_rate <= Decimal(1)):
                raise ValueError("error_rate must be between 0 and 1")
            if self.average_latency_ms < 0:
                raise ValueError("average_latency_ms cannot be negative")
        if self.seconds_since_last_success is not None and self.seconds_since_last_success < 0:
            raise ValueError("seconds_since_last_success cannot be negative")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        require_aware_datetime(self.computed_at, "computed_at")


def compute_provider_reliability(
    provider: str, outcomes: list[ProviderCallOutcome], now: datetime
) -> ProviderReliabilitySnapshot:
    """Score `provider` from its own recent `outcomes`. Fewer than `MIN_CALLS_FOR_STATUS` calls
    yields `INSUFFICIENT_DATA` -- a handful of samples cannot tell a real outage from noise, same
    "never a confident number from too little evidence" principle as Smart Money scoring."""

    for outcome in outcomes:
        if outcome.provider != provider:
            raise ValueError(
                f"outcome for {outcome.provider!r} does not match provider {provider!r}"
            )

    if len(outcomes) < MIN_CALLS_FOR_STATUS:
        return ProviderReliabilitySnapshot(
            provider=provider,
            status=ProviderReliabilityStatus.INSUFFICIENT_DATA,
            call_count=len(outcomes),
            error_rate=None,
            average_latency_ms=None,
            seconds_since_last_success=None,
            computed_at=now,
            reasons=(
                f"only {len(outcomes)} call(s) observed, need at least {MIN_CALLS_FOR_STATUS}",
            ),
        )

    failures = sum(1 for outcome in outcomes if not outcome.succeeded)
    error_rate = Decimal(failures) / Decimal(len(outcomes))
    average_latency_ms = sum((outcome.latency_ms for outcome in outcomes), Decimal(0)) / Decimal(
        len(outcomes)
    )
    successes = [outcome for outcome in outcomes if outcome.succeeded]
    last_success_at = max((outcome.occurred_at for outcome in successes), default=None)
    seconds_since_last_success = (
        None if last_success_at is None else Decimal(str((now - last_success_at).total_seconds()))
    )

    if (
        last_success_at is None
        or error_rate >= _UNRELIABLE_ERROR_RATE
        or average_latency_ms >= _UNRELIABLE_LATENCY_MS
    ):
        status = ProviderReliabilityStatus.UNRELIABLE
    elif error_rate >= _DEGRADED_ERROR_RATE or average_latency_ms >= _DEGRADED_LATENCY_MS:
        status = ProviderReliabilityStatus.DEGRADED
    else:
        status = ProviderReliabilityStatus.HEALTHY

    reasons = [
        f"error rate {error_rate:.0%} over {len(outcomes)} calls",
        f"average latency {average_latency_ms}ms",
    ]
    reasons.append(
        "no successful call observed" if last_success_at is None else "at least one recent success"
    )
    reasons.append(f"not evaluated: {', '.join(UNEVALUATED_DIMENSIONS)}")

    return ProviderReliabilitySnapshot(
        provider=provider,
        status=status,
        call_count=len(outcomes),
        error_rate=error_rate,
        average_latency_ms=average_latency_ms,
        seconds_since_last_success=seconds_since_last_success,
        computed_at=now,
        reasons=tuple(reasons),
    )
