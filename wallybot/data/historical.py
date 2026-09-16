"""Immutable, checksummed Parquet partitions with a sidecar manifest (ADR-005).

Write partitions like data/market/<venue>/<BASE>_<QUOTE>/<timeframe>/date=<date>/part-<id>.parquet,
finalized via a temp file + checksum + atomic rename, per DATA.md's "Market quality and historical
data" section. Corrections publish a new part (new part_id) rather than overwriting -- this never
silently rewrites a research input.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from wallybot.domain.clock import Clock
from wallybot.domain.id_generator import IdGenerator
from wallybot.domain.market import Candle

SCHEMA_VERSION = 1
_DECIMAL_TYPE = pa.decimal128(18, 8)

_SCHEMA = pa.schema(
    [
        ("venue", pa.string()),
        ("market_type", pa.string()),
        ("base", pa.string()),
        ("quote", pa.string()),
        ("timeframe", pa.string()),
        ("open_time", pa.timestamp("us", tz="UTC")),
        ("close_time", pa.timestamp("us", tz="UTC")),
        ("open", _DECIMAL_TYPE),
        ("high", _DECIMAL_TYPE),
        ("low", _DECIMAL_TYPE),
        ("close", _DECIMAL_TYPE),
        ("volume", _DECIMAL_TYPE),
        ("source", pa.string()),
        ("received_at", pa.timestamp("us", tz="UTC")),
    ]
)


@dataclass(frozen=True)
class PartitionManifest:
    part_id: str
    venue: str
    base: str
    quote: str
    timeframe: str
    date: str
    row_count: int
    source: str
    quality_status: str
    sha256: str
    schema_version: int
    window_start: datetime
    window_end: datetime
    written_at: datetime
    path: str


class HistoricalStore:
    def __init__(self, root: Path, clock: Clock, id_generator: IdGenerator) -> None:
        self.root = root
        self.clock = clock
        self.id_generator = id_generator

    def write_partition(self, candles: list[Candle], quality_status: str) -> PartitionManifest:
        instrument, timeframe, date = self._validate_homogeneous(candles)
        part_id = self.id_generator.new_id()
        partition_dir = (
            self.root
            / "market"
            / instrument.venue
            / f"{instrument.base}_{instrument.quote}"
            / timeframe
            / f"date={date}"
        )
        partition_dir.mkdir(parents=True, exist_ok=True)

        sha256 = self._write_parquet(partition_dir, part_id, candles)

        manifest = PartitionManifest(
            part_id=part_id,
            venue=instrument.venue,
            base=instrument.base,
            quote=instrument.quote,
            timeframe=timeframe,
            date=date,
            row_count=len(candles),
            source=candles[0].source,
            quality_status=quality_status,
            sha256=sha256,
            schema_version=SCHEMA_VERSION,
            window_start=min(c.open_time for c in candles),
            window_end=max(c.close_time for c in candles),
            written_at=self.clock.now(),
            path=str(partition_dir / f"part-{part_id}.parquet"),
        )
        self._write_manifest(partition_dir, part_id, manifest)
        return manifest

    def _validate_homogeneous(self, candles: list[Candle]) -> tuple:
        if not candles:
            raise ValueError("candles must not be empty")
        instrument = candles[0].instrument
        timeframe = candles[0].timeframe
        dates = set()
        for candle in candles:
            if candle.instrument != instrument:
                raise ValueError("all candles must share the same instrument")
            if candle.timeframe != timeframe:
                raise ValueError("all candles must share the same timeframe")
            dates.add(candle.open_time.date())
        if len(dates) != 1:
            raise ValueError("all candles must fall on the same UTC date")
        return instrument, timeframe, dates.pop().isoformat()

    def _write_parquet(self, partition_dir: Path, part_id: str, candles: list[Candle]) -> str:
        table = pa.Table.from_pylist(
            [
                {
                    "venue": c.instrument.venue,
                    "market_type": str(c.instrument.market_type),
                    "base": c.instrument.base,
                    "quote": c.instrument.quote,
                    "timeframe": c.timeframe,
                    "open_time": c.open_time,
                    "close_time": c.close_time,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                    "source": c.source,
                    "received_at": c.received_at,
                }
                for c in candles
            ],
            schema=_SCHEMA,
        )
        final_path = partition_dir / f"part-{part_id}.parquet"
        tmp_path = partition_dir / f".tmp-{part_id}.parquet"
        # fsync before the atomic rename: without it, a container kill/VM pause between the
        # rename and the OS flushing dirty pages can leave a *renamed* (i.e. seemingly published)
        # partition with truncated or zero-byte content -- observed in production on this host.
        with open(tmp_path, "wb") as f:
            pq.write_table(table, f)
            f.flush()
            os.fsync(f.fileno())
        sha256 = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        os.replace(tmp_path, final_path)
        return sha256

    def _write_manifest(
        self, partition_dir: Path, part_id: str, manifest: PartitionManifest
    ) -> None:
        payload = {
            "part_id": manifest.part_id,
            "venue": manifest.venue,
            "base": manifest.base,
            "quote": manifest.quote,
            "timeframe": manifest.timeframe,
            "date": manifest.date,
            "row_count": manifest.row_count,
            "source": manifest.source,
            "quality_status": manifest.quality_status,
            "sha256": manifest.sha256,
            "schema_version": manifest.schema_version,
            "window_start": manifest.window_start.isoformat(),
            "window_end": manifest.window_end.isoformat(),
            "written_at": manifest.written_at.isoformat(),
            "path": manifest.path,
        }
        final_path = partition_dir / f"part-{part_id}.manifest.json"
        tmp_path = partition_dir / f".tmp-{part_id}.manifest.json"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, indent=2))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
