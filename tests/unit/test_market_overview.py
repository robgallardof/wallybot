from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.application.market_overview import build_market_overview
from wallybot.data.quality import QualityPolicy
from wallybot.domain.quality import QualityStatus
from wallybot.exchanges.fake import FakeExchange
from wallybot.market.universe import UniverseFilterConfig


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


async def test_builds_an_overview_row_per_discovered_instrument():
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    provider = FakeExchange(clock=clock, seed=1)
    overview = await build_market_overview(
        provider=provider,
        clock=clock,
        timeframe="1h",
        history_candles=30,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        feature_window=20,
    )
    discovered = await provider.discover_instruments()
    assert len(overview.rows) == len(discovered)
    assert overview.as_of == clock.at
    for row in overview.rows:
        assert row.bid > 0
        assert row.ask >= row.bid


async def test_eligible_rows_get_a_score_and_rank_ineligible_do_not():
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    provider = FakeExchange(clock=clock, seed=1)
    overview = await build_market_overview(
        provider=provider,
        clock=clock,
        timeframe="1h",
        history_candles=30,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        feature_window=20,
    )
    for row in overview.rows:
        if row.eligible:
            assert row.score is not None
            assert row.rank is not None
        else:
            assert row.score is None
            assert row.rank is None


async def test_a_tighter_universe_config_produces_ineligible_rows_with_reasons():
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    provider = FakeExchange(clock=clock, seed=1)
    overview = await build_market_overview(
        provider=provider,
        clock=clock,
        timeframe="1h",
        history_candles=30,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("999999999"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        feature_window=20,
    )
    assert overview.rows
    for row in overview.rows:
        assert row.eligible is False
        assert "illiquid" in row.reasons


class StaleCandlesProvider:
    """Wraps a real provider but shifts one specific instrument's candles far into the past --
    simulates a provider that stopped updating a pair while everything else stays fresh."""

    def __init__(self, wrapped, stale_instrument_id: str, shift: timedelta) -> None:
        self._wrapped = wrapped
        self._stale_instrument_id = stale_instrument_id
        self._shift = shift

    async def discover_instruments(self):
        return await self._wrapped.discover_instruments()

    async def fetch_candles(self, instrument, timeframe, since, limit):
        candles = await self._wrapped.fetch_candles(instrument, timeframe, since, limit)
        if instrument.id != self._stale_instrument_id:
            return candles
        return [
            replace(
                candle,
                open_time=candle.open_time - self._shift,
                close_time=candle.close_time - self._shift,
                received_at=candle.received_at - self._shift,
            )
            for candle in candles
        ]

    async def fetch_snapshot(self, instrument):
        return await self._wrapped.fetch_snapshot(instrument)


async def test_failure_quality_instruments_are_ineligible_and_unranked():
    """ARCHITECTURE.md: "quality checks gate features" -- not just on the live trading path
    (wallybot.application.decision_pipeline already excludes FAILURE-quality candles before
    scoring), but here too: a FAILURE-quality instrument must never show up as eligible or ranked
    on the read-only Markets view either."""
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    wrapped = FakeExchange(clock=clock, seed=1)
    discovered = await wrapped.discover_instruments()
    stale_id = discovered[0].id
    provider = StaleCandlesProvider(wrapped, stale_id, timedelta(days=30))

    overview = await build_market_overview(
        provider=provider,
        clock=clock,
        timeframe="1h",
        history_candles=30,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        feature_window=20,
    )
    stale_row = next(row for row in overview.rows if row.instrument.id == stale_id)
    assert stale_row.quality.status == QualityStatus.FAILURE
    assert "data_quality_failure" in stale_row.reasons
    assert stale_row.eligible is False
    assert stale_row.score is None
    assert stale_row.rank is None
    # A fresh instrument elsewhere in the same universe is unaffected.
    fresh_row = next(row for row in overview.rows if row.instrument.id != stale_id)
    assert fresh_row.quality.status != QualityStatus.FAILURE


class FlakyProvider:
    """Wraps a real provider but always fails one specific instrument -- simulates a single
    delisted/unreachable pair among a wider discovered universe."""

    def __init__(self, wrapped, failing_instrument_id: str) -> None:
        self._wrapped = wrapped
        self._failing_instrument_id = failing_instrument_id

    async def discover_instruments(self):
        return await self._wrapped.discover_instruments()

    async def fetch_candles(self, instrument, timeframe, since, limit):
        if instrument.id == self._failing_instrument_id:
            raise ConnectionError("simulated provider outage")
        return await self._wrapped.fetch_candles(instrument, timeframe, since, limit)

    async def fetch_snapshot(self, instrument):
        if instrument.id == self._failing_instrument_id:
            raise ConnectionError("simulated provider outage")
        return await self._wrapped.fetch_snapshot(instrument)


async def test_one_failing_instrument_is_excluded_not_a_whole_overview_failure():
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    wrapped = FakeExchange(clock=clock, seed=1)
    discovered = await wrapped.discover_instruments()
    failing_id = discovered[0].id
    provider = FlakyProvider(wrapped, failing_id)

    overview = await build_market_overview(
        provider=provider,
        clock=clock,
        timeframe="1h",
        history_candles=30,
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        feature_window=20,
    )

    assert len(overview.rows) == len(discovered) - 1
    assert failing_id not in {row.instrument.id for row in overview.rows}
