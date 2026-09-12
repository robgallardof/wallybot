from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.application.scanner import scan_universe
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType
from wallybot.market.universe import UniverseFilterConfig

START = datetime(2026, 1, 1, tzinfo=UTC)
CONFIG = UniverseFilterConfig(
    version=1,
    min_history_candles=5,
    min_average_quote_volume=Decimal("10"),
    max_spread_ratio=Decimal("0.01"),
)


def make_instrument(base: str) -> Instrument:
    return Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base=base,
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.0001"),
        min_quantity=Decimal("0.0001"),
    )


def make_candles(instrument: Instrument, closes: list[str]) -> list[Candle]:
    candles = []
    for i, value in enumerate(closes):
        open_time = START + timedelta(hours=i)
        close = Decimal(value)
        candles.append(
            Candle(
                instrument=instrument,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=Decimal("1"),
                source="fake",
                received_at=open_time + timedelta(hours=1, seconds=1),
            )
        )
    return candles


def make_snapshot(instrument: Instrument) -> MarketSnapshot:
    return MarketSnapshot(
        instrument=instrument,
        bid=Decimal("99.9"),
        ask=Decimal("100"),
        timestamp=START + timedelta(hours=5),
        source="fake",
    )


def build_scenario():
    strong = make_instrument("BTC")
    weak = make_instrument("ETH")
    thin = make_instrument("XRP")

    strong_candles = make_candles(strong, ["100", "105", "110", "115", "120"])
    weak_candles = make_candles(weak, ["100", "99", "98", "97", "96"])
    thin_candles = make_candles(thin, ["100", "101", "102"])  # only 3: insufficient_history

    instruments = [strong, weak, thin]
    candles_by_instrument = {
        strong.id: strong_candles,
        weak.id: weak_candles,
        thin.id: thin_candles,
    }
    snapshots_by_instrument = {
        strong.id: make_snapshot(strong),
        weak.id: make_snapshot(weak),
        thin.id: make_snapshot(thin),
    }
    return instruments, candles_by_instrument, snapshots_by_instrument, strong, weak, thin


def test_scan_ranks_by_momentum_and_excludes_ineligible():
    instruments, candles, snapshots, strong, weak, thin = build_scenario()
    result = scan_universe(
        instruments,
        candles,
        snapshots,
        CONFIG,
        as_of=START + timedelta(hours=5),
        feature_window=5,
        max_finalists=5,
    )
    finalist_ids = [f.instrument_id for f in result.finalists]
    assert finalist_ids == [strong.id, weak.id]
    assert result.rejected_instrument_ids == (thin.id,)


def test_scan_respects_max_finalists():
    instruments, candles, snapshots, strong, weak, _thin = build_scenario()
    result = scan_universe(
        instruments,
        candles,
        snapshots,
        CONFIG,
        as_of=START + timedelta(hours=5),
        feature_window=5,
        max_finalists=1,
    )
    assert len(result.finalists) == 1
    assert result.finalists[0].instrument_id == strong.id


def test_scan_with_no_eligible_instruments_returns_empty_finalists():
    thin = make_instrument("XRP")
    thin_candles = make_candles(thin, ["100", "101", "102"])
    result = scan_universe(
        [thin],
        {thin.id: thin_candles},
        {thin.id: make_snapshot(thin)},
        CONFIG,
        as_of=START + timedelta(hours=5),
        feature_window=5,
        max_finalists=3,
    )
    assert result.finalists == ()
    assert result.rejected_instrument_ids == (thin.id,)


def test_scan_rejects_nonpositive_max_finalists():
    instruments, candles, snapshots, *_ = build_scenario()
    with pytest.raises(ValueError):
        scan_universe(
            instruments,
            candles,
            snapshots,
            CONFIG,
            as_of=START + timedelta(hours=5),
            feature_window=5,
            max_finalists=0,
        )
