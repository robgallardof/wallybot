from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from wallybot.application.market_ingestion import ingest_market_data
from wallybot.data.historical import HistoricalStore
from wallybot.data.quality import QualityPolicy
from wallybot.domain.market import Candle, Instrument, MarketType

BTC = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
ETH = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="ETH",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.001"),
    min_quantity=Decimal("0.001"),
)
NOW = datetime(2026, 1, 3, 6, tzinfo=UTC)
POLICY = QualityPolicy(
    version=1,
    timeframe="1h",
    max_stale_age=timedelta(hours=3),
    max_clock_drift=timedelta(minutes=5),
    max_abnormal_return=Decimal("0.5"),
)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


class SequentialIds:
    def __init__(self) -> None:
        self.counter = 0

    def new_id(self) -> str:
        self.counter += 1
        return f"id{self.counter}"


class FakeCursorStore:
    def __init__(self, seed: dict[tuple[str, str], datetime] | None = None) -> None:
        self._cursors = dict(seed or {})
        self.set_calls: list[tuple[str, str, datetime]] = []

    async def get(self, instrument_id: str, timeframe: str) -> datetime | None:
        return self._cursors.get((instrument_id, timeframe))

    async def set(self, instrument_id: str, timeframe: str, last_close_time: datetime) -> None:
        self._cursors[(instrument_id, timeframe)] = last_close_time
        self.set_calls.append((instrument_id, timeframe, last_close_time))


class FakeProvider:
    def __init__(
        self,
        instruments: list[Instrument],
        candles_by_instrument: dict[str, list[Candle]],
        errors: dict[str, Exception] | None = None,
    ) -> None:
        self.instruments = instruments
        self.candles_by_instrument = candles_by_instrument
        self.errors = errors or {}
        self.fetch_calls: list[tuple[str, datetime, int]] = []

    async def discover_instruments(self) -> list[Instrument]:
        return self.instruments

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        self.fetch_calls.append((instrument.id, since, limit))
        if instrument.id in self.errors:
            raise self.errors[instrument.id]
        return self.candles_by_instrument.get(instrument.id, [])


def make_candle(instrument: Instrument, open_time: datetime, close: str = "100") -> Candle:
    return Candle(
        instrument=instrument,
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1"),
        source="fake",
        received_at=open_time + timedelta(hours=1),
    )


def make_series(instrument: Instrument, start: datetime, hours: int) -> list[Candle]:
    return [make_candle(instrument, start + timedelta(hours=i)) for i in range(hours)]


def no_parquet_files_written(root: Path) -> bool:
    return list(root.rglob("*.parquet")) == []


async def test_bootstraps_with_no_cursor_and_writes_a_partition(tmp_path: Path):
    start = datetime(2026, 1, 3, 0, tzinfo=UTC)
    candles = make_series(BTC, start, 4)
    provider = FakeProvider([BTC], {BTC.id: candles})
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore()

    summary = await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    assert len(summary.outcomes) == 1
    outcome = summary.outcomes[0]
    assert outcome.fetched_candles == 4
    assert outcome.quality_status == "PASS"
    assert len(outcome.written_part_ids) == 1
    assert outcome.cursor == candles[-1].close_time
    assert await cursor_store.get(BTC.id, "1h") == candles[-1].close_time
    written_dir = tmp_path / "market" / "fake" / "BTC_USD" / "1h" / "date=2026-01-03"
    assert len(list(written_dir.glob("part-*.parquet"))) == 1


async def test_since_uses_existing_cursor_instead_of_bootstrap_lookback(tmp_path: Path):
    cursor_at = datetime(2026, 1, 3, 1, tzinfo=UTC)
    provider = FakeProvider([BTC], {BTC.id: []})
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore(seed={(BTC.id, "1h"): cursor_at})

    await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    assert provider.fetch_calls == [(BTC.id, cursor_at, 720)]


async def test_never_rewrites_candles_already_past_the_cursor(tmp_path: Path):
    start = datetime(2026, 1, 3, 0, tzinfo=UTC)
    candles = make_series(BTC, start, 4)
    cursor_at = candles[1].close_time
    provider = FakeProvider([BTC], {BTC.id: candles})  # provider replays the whole overlap
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore(seed={(BTC.id, "1h"): cursor_at})

    summary = await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    outcome = summary.outcomes[0]
    assert outcome.fetched_candles == 2  # only the two candles after the cursor
    assert outcome.cursor == candles[-1].close_time


async def test_failure_quality_skips_write_but_advances_cursor(tmp_path: Path):
    start = datetime(2026, 1, 3, 0, tzinfo=UTC)
    candles = make_series(BTC, start, 2)
    stale_now = candles[-1].close_time + timedelta(hours=6)  # older than max_stale_age=3h
    provider = FakeProvider([BTC], {BTC.id: candles})
    store = HistoricalStore(tmp_path, FixedClock(stale_now), SequentialIds())
    cursor_store = FakeCursorStore()

    summary = await ingest_market_data(
        provider, store, FixedClock(stale_now), "1h", POLICY, cursor_store
    )

    outcome = summary.outcomes[0]
    assert outcome.quality_status == "FAILURE"
    assert outcome.written_part_ids == ()
    assert outcome.cursor == candles[-1].close_time
    assert await cursor_store.get(BTC.id, "1h") == candles[-1].close_time
    assert no_parquet_files_written(tmp_path)


async def test_a_candle_batch_spanning_two_dates_writes_two_partitions(tmp_path: Path):
    start = datetime(2026, 1, 3, 22, tzinfo=UTC)
    candles = make_series(BTC, start, 4)  # 22:00, 23:00, 00:00 (Jan 4), 01:00 (Jan 4)
    provider = FakeProvider([BTC], {BTC.id: candles})
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore()

    summary = await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    outcome = summary.outcomes[0]
    assert len(outcome.written_part_ids) == 2
    assert (tmp_path / "market" / "fake" / "BTC_USD" / "1h" / "date=2026-01-03").exists()
    assert (tmp_path / "market" / "fake" / "BTC_USD" / "1h" / "date=2026-01-04").exists()
    # Cursor advances once per partition, in date order, ending at the latest close_time.
    assert cursor_store.set_calls[-1] == (BTC.id, "1h", candles[-1].close_time)


async def test_one_instrument_failing_does_not_block_the_others(tmp_path: Path):
    start = NOW - timedelta(hours=2)
    good = make_series(BTC, start, 2)
    provider = FakeProvider(
        [BTC, ETH],
        {BTC.id: good, ETH.id: []},
        errors={ETH.id: ConnectionError("boom")},
    )
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore()

    summary = await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    by_id = {o.instrument_id: o for o in summary.outcomes}
    assert by_id[BTC.id].error is None
    assert len(by_id[BTC.id].written_part_ids) == 1
    assert by_id[ETH.id].error == "ConnectionError: boom"
    assert by_id[ETH.id].cursor is None


async def test_empty_fetch_leaves_cursor_untouched(tmp_path: Path):
    provider = FakeProvider([BTC], {BTC.id: []})
    store = HistoricalStore(tmp_path, FixedClock(NOW), SequentialIds())
    cursor_store = FakeCursorStore()

    summary = await ingest_market_data(provider, store, FixedClock(NOW), "1h", POLICY, cursor_store)

    outcome = summary.outcomes[0]
    assert outcome.fetched_candles == 0
    assert outcome.cursor is None
    assert cursor_store.set_calls == []
