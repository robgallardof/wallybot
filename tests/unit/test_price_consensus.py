from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.price_consensus import (
    PriceConsensusResult,
    PriceConsensusStatus,
    PriceQuote,
    compute_price_consensus,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = "BTC/USD"


def quote(source: str, price: str, seconds_ago: int = 0) -> PriceQuote:
    return PriceQuote(
        source=source, price=Decimal(price), observed_at=NOW - timedelta(seconds=seconds_ago)
    )


def test_two_agreeing_fresh_quotes_produce_a_consensus() -> None:
    quotes = [quote("kraken", "50000"), quote("coinbase", "50010")]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert result.status is PriceConsensusStatus.CONSENSUS
    assert result.consensus_price == Decimal("50005")
    assert set(result.included_sources) == {"kraken", "coinbase"}


def test_a_single_quote_is_insufficient() -> None:
    result = compute_price_consensus(INSTRUMENT, [quote("kraken", "50000")], NOW)
    assert result.status is PriceConsensusStatus.INSUFFICIENT_DATA
    assert result.consensus_price is None


def test_no_quotes_at_all_is_insufficient() -> None:
    result = compute_price_consensus(INSTRUMENT, [], NOW)
    assert result.status is PriceConsensusStatus.INSUFFICIENT_DATA


def test_a_stale_quote_is_excluded_before_consensus() -> None:
    quotes = [
        quote("kraken", "50000", seconds_ago=10),
        quote("coinbase", "50010", seconds_ago=10),
        quote("stale-source", "1", seconds_ago=10_000),
    ]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert result.status is PriceConsensusStatus.CONSENSUS
    assert "stale-source" not in result.included_sources
    assert "stale-source" in result.excluded_sources


def test_only_stale_quotes_available_is_insufficient() -> None:
    quotes = [
        quote("kraken", "50000", seconds_ago=10_000),
        quote("coinbase", "50010", seconds_ago=10_000),
    ]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert result.status is PriceConsensusStatus.INSUFFICIENT_DATA


def test_an_outlier_quote_is_excluded_from_the_consensus_price() -> None:
    quotes = [
        quote("kraken", "50000"),
        quote("coinbase", "50010"),
        quote("bad-feed", "100000"),
    ]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert result.status is PriceConsensusStatus.CONSENSUS
    assert "bad-feed" not in result.included_sources
    assert "bad-feed" in result.excluded_sources
    assert result.consensus_price == Decimal("50005")


def test_when_too_few_quotes_survive_outlier_filtering_it_is_insufficient() -> None:
    quotes = [quote("kraken", "50000"), quote("bad-feed", "100000")]
    result = compute_price_consensus(INSTRUMENT, quotes, NOW)
    assert result.status is PriceConsensusStatus.INSUFFICIENT_DATA


def test_max_staleness_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_staleness must be positive"):
        compute_price_consensus(INSTRUMENT, [], NOW, max_staleness=timedelta(0))


def test_outlier_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="outlier_threshold_pct must be positive"):
        compute_price_consensus(INSTRUMENT, [], NOW, outlier_threshold_pct=Decimal(0))


def test_a_consensus_result_must_carry_a_price() -> None:
    with pytest.raises(ValueError, match="must carry a consensus_price"):
        PriceConsensusResult(
            instrument_id=INSTRUMENT,
            status=PriceConsensusStatus.CONSENSUS,
            consensus_price=None,
            included_sources=("kraken", "coinbase"),
            excluded_sources=(),
            reasons=("x",),
            computed_at=NOW,
        )


def test_an_insufficient_data_result_must_not_carry_a_price() -> None:
    with pytest.raises(ValueError, match="must not carry a consensus_price"):
        PriceConsensusResult(
            instrument_id=INSTRUMENT,
            status=PriceConsensusStatus.INSUFFICIENT_DATA,
            consensus_price=Decimal("50000"),
            included_sources=(),
            excluded_sources=("kraken",),
            reasons=("x",),
            computed_at=NOW,
        )
