"""DuckDB-backed reader over ADR-005's immutable, checksummed Parquet partitions.

Every manifest's recorded `sha256` is re-verified against the actual file on disk before that
partition is ever included in a query -- ADR-005's "checksummed manifests" is a guarantee this
reader enforces, not just a fact `HistoricalStore` happens to record. A manifest whose
`schema_version` does not match this reader's `SUPPORTED_SCHEMA_VERSION` is rejected outright
rather than read with a guessed column mapping -- an unversioned assumption here could silently
feed backtests bad data. DuckDB itself is configured with an explicit memory/thread ceiling per
run (never inherited from a shared long-lived process) per PENDING.md's Phase 5 "límites de
recursos" requirement.

The caller passes the `Instrument` being queried (the same object an exchange adapter already
returns) rather than this reader reconstructing one from Parquet columns: the stored columns only
carry identity (venue/market_type/base/quote), never price/quantity increments or minimum size --
inventing those here would repeat the exact "never fabricate a precision field" mistake
`TradeProposalRepository`'s docstring already documents avoiding. Each row's identity columns are
still checked against the supplied `Instrument` as a defensive consistency check, not a source of
truth.

Pure query layer: no writes, no mutation of any manifest or Parquet file.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from wallybot.data.historical import SCHEMA_VERSION
from wallybot.domain.market import Candle, Instrument

SUPPORTED_SCHEMA_VERSION = SCHEMA_VERSION


class ManifestIntegrityError(ValueError):
    """A partition's Parquet file no longer matches the sha256 recorded in its own manifest."""


class UnsupportedSchemaVersion(ValueError):
    """A manifest was written by a schema version this reader does not know how to interpret."""


class PartitionIdentityMismatch(ValueError):
    """A Parquet row's own venue/base/quote does not match the Instrument the caller queried
    for -- the partition directory layout and the row contents have drifted apart."""


@dataclass(frozen=True)
class QueryResourceLimits:
    memory_limit: str = "512MB"
    threads: int = 2

    def __post_init__(self) -> None:
        if self.threads < 1:
            raise ValueError("threads must be positive")


DEFAULT_QUERY_LIMITS = QueryResourceLimits()


def _verified_partition_paths(base_dir: Path) -> list[Path]:
    """Every `*.manifest.json` under `base_dir` (recursively, across `date=...` partitions),
    each checked against its own recorded checksum before its Parquet file is trusted."""
    verified: list[Path] = []
    for manifest_path in sorted(base_dir.rglob("*.manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != SUPPORTED_SCHEMA_VERSION:
            raise UnsupportedSchemaVersion(
                f"{manifest_path} was written with schema_version={manifest['schema_version']}, "
                f"this reader only supports {SUPPORTED_SCHEMA_VERSION}"
            )
        parquet_path = Path(manifest["path"])
        if not parquet_path.is_absolute():
            parquet_path = manifest_path.parent / parquet_path.name
        actual_sha256 = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
        if actual_sha256 != manifest["sha256"]:
            raise ManifestIntegrityError(
                f"{parquet_path} does not match the sha256 recorded in {manifest_path}"
            )
        verified.append(parquet_path)
    return verified


def read_candles(
    root: Path,
    instrument: Instrument,
    timeframe: str,
    start: datetime,
    end: datetime,
    limits: QueryResourceLimits = DEFAULT_QUERY_LIMITS,
) -> list[Candle]:
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be aware datetimes")
    if end < start:
        raise ValueError("end must not be before start")

    partition_base = (
        root / "market" / instrument.venue / f"{instrument.base}_{instrument.quote}" / timeframe
    )
    if not partition_base.exists():
        return []

    paths = _verified_partition_paths(partition_base)
    if not paths:
        return []

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"SET memory_limit='{limits.memory_limit}'")
        connection.execute(f"SET threads={limits.threads}")
        # Without this, DuckDB's Python client converts TIMESTAMPTZ columns to the host's local
        # timezone on fetch -- silently corrupting every UTC boundary this codebase relies on.
        connection.execute("SET TimeZone='UTC'")
        rows = connection.execute(
            "SELECT venue, base, quote, open_time, close_time, "
            "open, high, low, close, volume, source, received_at "
            "FROM read_parquet(?) "
            "WHERE open_time >= ? AND close_time <= ? "
            "ORDER BY open_time",
            [[str(path) for path in paths], start, end],
        ).fetchall()
    finally:
        connection.close()

    candles = []
    for row in rows:
        row_identity = (row[0], row[1], row[2])
        expected_identity = (instrument.venue, instrument.base, instrument.quote)
        if row_identity != expected_identity:
            raise PartitionIdentityMismatch(
                f"row identity {row_identity} does not match queried instrument {expected_identity}"
            )
        candles.append(
            Candle(
                instrument=instrument,
                timeframe=timeframe,
                open_time=row[3],
                close_time=row[4],
                open=row[5],
                high=row[6],
                low=row[7],
                close=row[8],
                volume=row[9],
                source=row[10],
                received_at=row[11],
            )
        )
    return candles
