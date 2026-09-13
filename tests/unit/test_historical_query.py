import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from wallybot.data.historical import HistoricalStore
from wallybot.data.historical_query import (
    ManifestIntegrityError,
    QueryResourceLimits,
    UnsupportedSchemaVersion,
    read_candles,
)
from wallybot.domain.market import Candle, Instrument, MarketType

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
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


def make_candle(open_time: datetime, close: str = "100") -> Candle:
    return Candle(
        instrument=INSTRUMENT,
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1.5"),
        source="fake",
        received_at=open_time + timedelta(hours=1, seconds=1),
    )


def make_store(tmp_path: Path) -> HistoricalStore:
    return HistoricalStore(tmp_path, FixedClock(datetime(2026, 1, 1, tzinfo=UTC)), SequentialIds())


def test_reads_back_written_candles_within_range(tmp_path):
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    written = [make_candle(start), make_candle(start + timedelta(hours=1))]
    store.write_partition(written, "PASS")

    result = read_candles(tmp_path, INSTRUMENT, "1h", start, start + timedelta(hours=2))

    assert len(result) == 2
    assert [c.open_time for c in result] == [c.open_time for c in written]
    assert all(c.instrument == INSTRUMENT for c in result)


def test_range_filter_excludes_candles_whose_close_falls_outside_the_window(tmp_path):
    # A candle is included only when it fully closes within [start, end] -- the same "no partial
    # future observation" boundary FeatureEngine already enforces, applied to a range query.
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    store.write_partition([make_candle(start), make_candle(start + timedelta(hours=1))], "PASS")

    result = read_candles(tmp_path, INSTRUMENT, "1h", start, start + timedelta(hours=1, minutes=30))

    assert len(result) == 1
    assert result[0].open_time == start


def test_missing_partition_directory_returns_empty_list(tmp_path):
    result = read_candles(
        tmp_path,
        INSTRUMENT,
        "1h",
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
    )
    assert result == []


def test_naive_datetime_bounds_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="aware"):
        read_candles(
            tmp_path,
            INSTRUMENT,
            "1h",
            datetime(2026, 1, 1),
            datetime(2026, 1, 2, tzinfo=UTC),
        )


def test_end_before_start_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="end must not be before start"):
        read_candles(
            tmp_path,
            INSTRUMENT,
            "1h",
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_a_tampered_parquet_file_is_rejected_even_though_the_manifest_looks_fine(tmp_path):
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    manifest = store.write_partition([make_candle(start)], "PASS")
    Path(manifest.path).write_bytes(b"not a real parquet file anymore")

    with pytest.raises(ManifestIntegrityError):
        read_candles(tmp_path, INSTRUMENT, "1h", start, start + timedelta(hours=1))


def test_an_unsupported_schema_version_is_rejected(tmp_path):
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    store.write_partition([make_candle(start)], "PASS")
    manifest_path = next(tmp_path.rglob("*.manifest.json"))
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(UnsupportedSchemaVersion):
        read_candles(tmp_path, INSTRUMENT, "1h", start, start + timedelta(hours=1))


def test_resource_limits_reject_nonpositive_threads() -> None:
    with pytest.raises(ValueError, match="threads"):
        QueryResourceLimits(threads=0)
