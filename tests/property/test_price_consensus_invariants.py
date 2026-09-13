from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.price_consensus import (
    PriceConsensusStatus,
    PriceQuote,
    compute_price_consensus,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = "BTC/USD"

_price = st.decimals(
    min_value="1", max_value="1000000", places=2, allow_nan=False, allow_infinity=False
)
_age_seconds = st.integers(min_value=0, max_value=600)


def _make_quote(index: int, price: Decimal, age_seconds: int) -> PriceQuote:
    return PriceQuote(
        source=f"source-{index}",
        price=price,
        observed_at=NOW - timedelta(seconds=age_seconds),
    )


@given(entries=st.lists(st.tuples(_price, _age_seconds), min_size=0, max_size=10))
@settings(max_examples=200)
def test_a_consensus_price_is_always_positive_and_from_a_real_subset_of_sources(entries):
    quotes = [_make_quote(i, price, age) for i, (price, age) in enumerate(entries)]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)

    all_sources = {q.source for q in quotes}
    assert set(result.included_sources) <= all_sources
    assert set(result.excluded_sources) <= all_sources
    assert not (set(result.included_sources) & set(result.excluded_sources))

    if result.status is PriceConsensusStatus.CONSENSUS:
        assert result.consensus_price is not None
        assert result.consensus_price > 0
        assert len(result.included_sources) >= 2
    else:
        assert result.consensus_price is None


@given(entries=st.lists(st.tuples(_price, _age_seconds), min_size=0, max_size=10))
@settings(max_examples=100)
def test_computing_consensus_twice_is_deterministic(entries):
    quotes = [_make_quote(i, price, age) for i, (price, age) in enumerate(entries)]
    first = compute_price_consensus(INSTRUMENT, quotes, NOW)
    second = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert first == second
