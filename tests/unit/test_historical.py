import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from wallybot.data.historical import HistoricalStore
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


def make_candle(open_time: datetime, instrument: Instrument = INSTRUMENT) -> Candle:
    return Candle(
        instrument=instrument,
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal("100"),
        high=Decimal("100"),
        low=Decimal("100"),
        close=Decimal("100"),
        volume=Decimal("1.5"),
        source="fake",
        received_at=open_time + timedelta(hours=1, seconds=1),
    )


def make_store(tmp_path: Path) -> HistoricalStore:
    return HistoricalStore(tmp_path, FixedClock(datetime(2026, 1, 1, tzinfo=UTC)), SequentialIds())


def test_writes_partition_and_manifest(tmp_path):
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [make_candle(start), make_candle(start + timedelta(hours=1))]
    manifest = store.write_partition(candles, quality_status="PASS")

    expected_dir = tmp_path / "market" / "fake" / "BTC_USD" / "1h" / "date=2026-01-01"
    assert (expected_dir / "part-id1.parquet").exists()
    assert (expected_dir / "part-id1.manifest.json").exists()
    assert manifest.row_count == 2
    assert manifest.quality_status == "PASS"
    assert manifest.date == "2026-01-01"

    table = pq.read_table(expected_dir / "part-id1.parquet")
    assert table.num_rows == 2


def test_manifest_sha256_matches_written_file(tmp_path):
    store = make_store(tmp_path)
    manifest = store.write_partition([make_candle(datetime(2026, 1, 1, tzinfo=UTC))], "PASS")
    actual = hashlib.sha256(Path(manifest.path).read_bytes()).hexdigest()
    assert actual == manifest.sha256


def test_no_temp_files_left_behind(tmp_path):
    store = make_store(tmp_path)
    store.write_partition([make_candle(datetime(2026, 1, 1, tzinfo=UTC))], "PASS")
    assert list(tmp_path.rglob(".tmp-*")) == []


def test_rejects_empty_candles(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.write_partition([], "PASS")


def test_rejects_mixed_instruments(tmp_path):
    other = Instrument(
        venue="fake",
        market_type=MarketType.SPOT,
        base="ETH",
        quote="USD",
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
    )
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = [make_candle(start), make_candle(start + timedelta(hours=1), instrument=other)]
    with pytest.raises(ValueError):
        store.write_partition(candles, "PASS")


def test_rejects_mixed_dates(tmp_path):
    store = make_store(tmp_path)
    candles = [
        make_candle(datetime(2026, 1, 1, 23, tzinfo=UTC)),
        make_candle(datetime(2026, 1, 2, 0, tzinfo=UTC)),
    ]
    with pytest.raises(ValueError):
        store.write_partition(candles, "PASS")


def test_correction_writes_a_new_part_instead_of_overwriting(tmp_path):
    store = make_store(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    first = store.write_partition([make_candle(start)], "PASS")
    second = store.write_partition([make_candle(start)], "WARNING")
    assert first.part_id != second.part_id
    assert Path(first.path).exists()
    assert Path(second.path).exists()
