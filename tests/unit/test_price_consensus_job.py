from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.application.price_consensus_job import (
    TRACKED_PAIRS,
    ProviderSource,
    compute_price_consensus_and_reliability,
)
from wallybot.domain.market import Candle, Instrument
from wallybot.domain.price_consensus import PriceConsensusStatus
from wallybot.domain.provider_reliability import ProviderReliabilityStatus

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _candle(instrument: Instrument, close: str, close_time: datetime) -> Candle:
    return Candle(
        instrument=instrument,
        timeframe="1m",
        open_time=close_time - timedelta(minutes=1),
        close_time=close_time,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1"),
        source=instrument.venue,
        received_at=close_time,
    )


class FakeCandleProvider:
    def __init__(self, price: str, *, fails: bool = False, stale: bool = False) -> None:
        self.price = price
        self.fails = fails
        self.stale = stale
        self.calls: list[Instrument] = []

    async def discover_instruments(self) -> list[Instrument]:
        raise NotImplementedError

    async def fetch_candles(self, instrument, timeframe, since, limit):
        self.calls.append(instrument)
        if self.fails:
            raise ConnectionError("simulated network failure")
        close_time = NOW - timedelta(minutes=30) if self.stale else NOW
        return [_candle(instrument, self.price, close_time)]

    async def fetch_snapshot(self, instrument):
        raise NotImplementedError


async def test_two_agreeing_providers_reach_consensus_for_every_tracked_pair() -> None:
    kraken = FakeCandleProvider("100")
    tiingo = FakeCandleProvider("100.5")
    sources = [ProviderSource("kraken", kraken), ProviderSource("tiingo", tiingo)]
    outcomes = {}

    results, snapshots = await compute_price_consensus_and_reliability(sources, NOW, outcomes)

    assert len(results) == len(TRACKED_PAIRS)
    assert {result.instrument_id for result in results} == {pair for pair, _ in TRACKED_PAIRS}
    for result in results:
        assert result.status is PriceConsensusStatus.CONSENSUS
        assert set(result.included_sources) == {"kraken", "tiingo"}
    # One call per tracked pair for each provider.
    assert len(kraken.calls) == len(TRACKED_PAIRS)
    assert len(tiingo.calls) == len(TRACKED_PAIRS)
    # Fewer than MIN_CALLS_FOR_STATUS (5) calls so far -- reliability is not yet confident.
    assert {snapshot.provider for snapshot in snapshots} == {"kraken", "tiingo"}
    assert all(
        snapshot.status is ProviderReliabilityStatus.INSUFFICIENT_DATA for snapshot in snapshots
    )


async def test_only_one_configured_provider_never_fabricates_a_consensus() -> None:
    sources = [ProviderSource("kraken", FakeCandleProvider("100"))]
    outcomes = {}

    results, _ = await compute_price_consensus_and_reliability(sources, NOW, outcomes)

    assert all(result.status is PriceConsensusStatus.INSUFFICIENT_DATA for result in results)
    assert all(result.consensus_price is None for result in results)


async def test_a_stale_quote_is_excluded_and_reported_as_insufficient() -> None:
    sources = [
        ProviderSource("kraken", FakeCandleProvider("100")),
        ProviderSource("tiingo", FakeCandleProvider("100", stale=True)),
    ]
    outcomes = {}

    results, _ = await compute_price_consensus_and_reliability(sources, NOW, outcomes)

    for result in results:
        assert result.status is PriceConsensusStatus.INSUFFICIENT_DATA
        assert "tiingo" in result.excluded_sources


async def test_a_failing_provider_is_recorded_as_an_unsuccessful_outcome_not_a_quote() -> None:
    sources = [
        ProviderSource("kraken", FakeCandleProvider("100")),
        ProviderSource("tiingo", FakeCandleProvider("100", fails=True)),
    ]
    outcomes = {}

    results, snapshots = await compute_price_consensus_and_reliability(sources, NOW, outcomes)

    assert all(result.status is PriceConsensusStatus.INSUFFICIENT_DATA for result in results)
    tiingo_outcomes = outcomes["tiingo"]
    assert len(tiingo_outcomes) == len(TRACKED_PAIRS)
    assert all(not outcome.succeeded for outcome in tiingo_outcomes)


async def test_repeated_ticks_accumulate_outcomes_until_reliability_is_confident() -> None:
    sources = [ProviderSource("kraken", FakeCandleProvider("100"))]
    outcomes = {}
    snapshots = []

    for _ in range(3):
        _, snapshots = await compute_price_consensus_and_reliability(sources, NOW, outcomes)

    # 3 ticks x len(TRACKED_PAIRS) calls each = enough to cross MIN_CALLS_FOR_STATUS (5).
    kraken_snapshot = next(s for s in snapshots if s.provider == "kraken")
    assert kraken_snapshot.status is ProviderReliabilityStatus.HEALTHY


async def test_binance_is_queried_for_usdt_and_never_combined_with_usd():
    binance = FakeCandleProvider("100")
    tiingo = FakeCandleProvider("100")
    results, snapshots = await compute_price_consensus_and_reliability(
        [ProviderSource("binance", binance), ProviderSource("tiingo", tiingo)], NOW, {}
    )
    by_pair = {result.instrument_id: result for result in results}
    assert set(by_pair) == {"BTC/USDT", "ETH/USDT", "BTC/USD", "ETH/USD"}
    assert {instrument.quote for instrument in binance.calls} == {"USDT"}
    assert {instrument.quote for instrument in tiingo.calls} == {"USD"}
    assert all(result.status is PriceConsensusStatus.INSUFFICIENT_DATA for result in results)
    assert all(result.consensus_price is None for result in results)
    assert {snapshot.provider for snapshot in snapshots} == {"binance", "tiingo"}


async def test_binance_failures_are_recorded_without_borrowing_usd_quotes():
    results, snapshots = await compute_price_consensus_and_reliability(
        [ProviderSource("binance", FakeCandleProvider("100", fails=True))], NOW, {}
    )
    assert {result.instrument_id for result in results} == {"BTC/USDT", "ETH/USDT"}
    assert all(result.consensus_price is None for result in results)
    assert snapshots[0].provider == "binance"
