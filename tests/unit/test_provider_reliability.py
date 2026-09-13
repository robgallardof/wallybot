from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.provider_reliability import (
    MIN_CALLS_FOR_STATUS,
    ProviderCallOutcome,
    ProviderReliabilitySnapshot,
    ProviderReliabilityStatus,
    compute_provider_reliability,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PROVIDER = "kraken"


def make_outcome(
    offset_seconds: int, succeeded: bool = True, latency_ms: str = "100"
) -> ProviderCallOutcome:
    return ProviderCallOutcome(
        provider=PROVIDER,
        succeeded=succeeded,
        latency_ms=Decimal(latency_ms),
        occurred_at=NOW - timedelta(seconds=offset_seconds),
    )


def test_fewer_than_the_minimum_calls_yields_insufficient_data() -> None:
    outcomes = [make_outcome(i) for i in range(MIN_CALLS_FOR_STATUS - 1)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.INSUFFICIENT_DATA
    assert snapshot.error_rate is None
    assert snapshot.average_latency_ms is None


def test_all_successful_low_latency_calls_are_healthy() -> None:
    outcomes = [make_outcome(i, succeeded=True, latency_ms="50") for i in range(10)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.HEALTHY
    assert snapshot.error_rate == Decimal(0)
    assert snapshot.average_latency_ms == Decimal("50")


def test_a_moderate_error_rate_is_degraded() -> None:
    outcomes = [make_outcome(i, succeeded=(i % 10 != 0)) for i in range(10)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.DEGRADED


def test_a_high_error_rate_is_unreliable() -> None:
    outcomes = [make_outcome(i, succeeded=(i % 2 == 0)) for i in range(10)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.UNRELIABLE


def test_high_latency_alone_is_degraded() -> None:
    outcomes = [make_outcome(i, succeeded=True, latency_ms="2500") for i in range(10)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.DEGRADED


def test_no_successful_call_at_all_is_unreliable_even_with_low_error_rate_math() -> None:
    outcomes = [make_outcome(i, succeeded=False) for i in range(10)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.status is ProviderReliabilityStatus.UNRELIABLE
    assert snapshot.seconds_since_last_success is None


def test_seconds_since_last_success_reflects_the_most_recent_success() -> None:
    outcomes = [
        make_outcome(300, succeeded=True),
        make_outcome(60, succeeded=True),
        make_outcome(30, succeeded=False),
        make_outcome(20, succeeded=False),
        make_outcome(10, succeeded=False),
    ]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert snapshot.seconds_since_last_success == Decimal("60")


def test_an_outcome_for_a_different_provider_is_rejected() -> None:
    outcomes = [make_outcome(i) for i in range(MIN_CALLS_FOR_STATUS)]
    with pytest.raises(ValueError, match="does not match provider"):
        compute_provider_reliability("coingecko", outcomes, NOW)


def test_reasons_always_list_the_unevaluated_dimensions_when_computed() -> None:
    outcomes = [make_outcome(i) for i in range(MIN_CALLS_FOR_STATUS)]
    snapshot = compute_provider_reliability(PROVIDER, outcomes, NOW)
    assert any("not evaluated" in reason for reason in snapshot.reasons)


def test_a_computed_status_must_carry_metrics() -> None:
    with pytest.raises(ValueError, match="must carry error_rate"):
        ProviderReliabilitySnapshot(
            provider=PROVIDER,
            status=ProviderReliabilityStatus.HEALTHY,
            call_count=10,
            error_rate=None,
            average_latency_ms=None,
            seconds_since_last_success=None,
            computed_at=NOW,
            reasons=("x",),
        )


def test_an_insufficient_data_snapshot_must_not_carry_metrics() -> None:
    with pytest.raises(ValueError, match="must not carry computed metrics"):
        ProviderReliabilitySnapshot(
            provider=PROVIDER,
            status=ProviderReliabilityStatus.INSUFFICIENT_DATA,
            call_count=2,
            error_rate=Decimal("0.1"),
            average_latency_ms=Decimal("50"),
            seconds_since_last_success=None,
            computed_at=NOW,
            reasons=("x",),
        )
