from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.data.quality import QualityPolicy, QualityStatus, evaluate_series_quality
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
START = datetime(2026, 1, 1, tzinfo=UTC)
POLICY = QualityPolicy(
    version=1,
    timeframe="1h",
    max_stale_age=timedelta(hours=2),
    max_clock_drift=timedelta(seconds=30),
    max_abnormal_return=Decimal("0.2"),
)


def make_candle(
    open_time,
    close=Decimal("100"),
    timeframe="1h",
    received_delay=timedelta(seconds=1),
):
    return Candle(
        instrument=INSTRUMENT,
        timeframe=timeframe,
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=Decimal("100"),
        high=max(Decimal("100"), close),
        low=min(Decimal("100"), close),
        close=close,
        volume=Decimal("1"),
        source="fake",
        received_at=open_time + timedelta(hours=1) + received_delay,
    )


def clean_series(count=3):
    return [make_candle(START + timedelta(hours=i)) for i in range(count)]


def test_clean_series_passes():
    now = START + timedelta(hours=3, seconds=1)
    report = evaluate_series_quality(clean_series(), POLICY, now=now)
    assert report.status == QualityStatus.PASS
    assert report.issues == ()


def test_empty_series_fails():
    report = evaluate_series_quality([], POLICY, now=START)
    assert report.status == QualityStatus.FAILURE
    assert report.issues[0].reason == "gap_detected"


def test_wrong_timeframe_fails():
    candles = [make_candle(START, timeframe="5m")]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=1))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "wrong_timeframe" for i in report.issues)


def test_not_ordered_fails():
    candles = [make_candle(START + timedelta(hours=1)), make_candle(START)]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=2))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "not_ordered" for i in report.issues)


def test_duplicate_timestamps_fails():
    candles = [make_candle(START), make_candle(START)]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=1))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "duplicate_timestamps" for i in report.issues)


def test_misaligned_timestamp_fails():
    candles = [make_candle(START + timedelta(minutes=15))]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=1))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "misaligned_timestamp" for i in report.issues)


def test_gap_detected_fails():
    candles = [make_candle(START), make_candle(START + timedelta(hours=2))]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=3))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "gap_detected" for i in report.issues)


def test_stale_fails():
    report = evaluate_series_quality(clean_series(), POLICY, now=START + timedelta(hours=10))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "stale" for i in report.issues)


def test_clock_drift_impossible_fails():
    candles = [make_candle(START, received_delay=timedelta(hours=-2))]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=1))
    assert report.status == QualityStatus.FAILURE
    assert any(i.reason == "clock_drift_impossible" for i in report.issues)


def test_clock_drift_is_warning_only():
    candles = [make_candle(START, received_delay=timedelta(minutes=5))]
    report = evaluate_series_quality(candles, POLICY, now=START + timedelta(hours=1))
    assert report.status == QualityStatus.WARNING
    assert [i.reason for i in report.issues] == ["clock_drift"]


def test_abnormal_return_is_warning_only():
    candles = [
        make_candle(START, close=Decimal("100")),
        make_candle(START + timedelta(hours=1), close=Decimal("200")),
    ]
    now = START + timedelta(hours=2, seconds=1)
    report = evaluate_series_quality(candles, POLICY, now=now)
    assert report.status == QualityStatus.WARNING
    assert [i.reason for i in report.issues] == ["abnormal_return"]


def test_policy_rejects_unsupported_timeframe():
    with pytest.raises(ValueError):
        QualityPolicy(
            version=1,
            timeframe="3m",
            max_stale_age=timedelta(hours=1),
            max_clock_drift=timedelta(seconds=1),
            max_abnormal_return=Decimal("0.1"),
        )
