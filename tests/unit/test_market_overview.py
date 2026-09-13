from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.application.market_overview import build_market_overview
from wallybot.data.quality import QualityPolicy
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
