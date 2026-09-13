from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.provider_reliability import (
    MIN_CALLS_FOR_STATUS,
    ProviderCallOutcome,
    ProviderReliabilityStatus,
    compute_provider_reliability,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
PROVIDER = "kraken"


def _make_outcome(index: int, succeeded: bool, latency_ms: Decimal) -> ProviderCallOutcome:
    return ProviderCallOutcome(
        provider=PROVIDER,
        succeeded=succeeded,
        latency_ms=latency_ms,
        occurred_at=NOW - timedelta(seconds=index),
    )


_latency = st.decimals(
    min_value="0", max_value="10000", places=2, allow_nan=False, allow_infinity=False
)


@given(outcomes=st.lists(st.tuples(st.booleans(), _latency), min_size=0, max_size=20))
@settings(max_examples=200)
def test_status_always_matches_whether_the_minimum_call_count_was_reached(outcomes):
    calls = [
        _make_outcome(i, succeeded, latency) for i, (succeeded, latency) in enumerate(outcomes)
    ]
    snapshot = compute_provider_reliability(PROVIDER, calls, NOW)
    assert snapshot.call_count == len(calls)

    if len(calls) < MIN_CALLS_FOR_STATUS:
        assert snapshot.status is ProviderReliabilityStatus.INSUFFICIENT_DATA
        assert snapshot.error_rate is None
    else:
        assert snapshot.status is not ProviderReliabilityStatus.INSUFFICIENT_DATA
        assert snapshot.error_rate is not None
        assert Decimal(0) <= snapshot.error_rate <= Decimal(1)
        assert snapshot.average_latency_ms is not None
        assert snapshot.average_latency_ms >= 0


@given(
    outcomes=st.lists(
        st.tuples(st.booleans(), _latency), min_size=MIN_CALLS_FOR_STATUS, max_size=20
    )
)
@settings(max_examples=100)
def test_scoring_the_same_outcomes_twice_is_deterministic(outcomes):
    calls = [
        _make_outcome(i, succeeded, latency) for i, (succeeded, latency) in enumerate(outcomes)
    ]
    first = compute_provider_reliability(PROVIDER, calls, NOW)
    second = compute_provider_reliability(PROVIDER, calls, NOW)
    assert first == second
