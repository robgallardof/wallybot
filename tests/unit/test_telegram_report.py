from datetime import UTC, datetime
from decimal import Decimal

from wallybot.domain.breaker import Breaker, BreakerType
from wallybot.domain.telegram_report import (
    EquityWindow,
    ReportInputs,
    ReportPeriod,
    ReportSeverity,
    ServiceHeartbeat,
    build_report_content,
)

NOW = datetime(2026, 1, 8, 0, 0, tzinfo=UTC)
PERIOD_START = datetime(2026, 1, 7, 0, 0, tzinfo=UTC)

HEALTHY_HEARTBEATS = tuple(
    ServiceHeartbeat(service=service, age_seconds=5, stale=False)
    for service in ("api", "worker", "scheduler", "research")
)


def _inputs(**overrides) -> ReportInputs:
    defaults = dict(
        period=ReportPeriod.DAILY,
        environment="PAPER",
        period_start=PERIOD_START,
        now=NOW,
        equity=EquityWindow(starting_equity=Decimal("1000"), current_equity=Decimal("1100")),
        total_fees=Decimal("2.50"),
        active_breakers=(),
        heartbeats=HEALTHY_HEARTBEATS,
    )
    defaults.update(overrides)
    return ReportInputs(**defaults)


def test_a_clean_period_is_info_severity_and_reports_the_return() -> None:
    content = build_report_content(_inputs())

    assert content.severity is ReportSeverity.INFO
    assert "Start 1000 -> Current 1100 (+10.00%)" in content.body
    assert "Costs: 2.50 in fees this period." in content.body
    assert "No active breakers." in content.body
    assert "Reconciliation: healthy" in content.body


def test_missing_equity_data_is_stated_rather_than_fabricated() -> None:
    content = build_report_content(
        _inputs(equity=EquityWindow(starting_equity=None, current_equity=None))
    )

    assert "No equity snapshot recorded for this period yet." in content.body
    assert "None" not in content.body


def test_benchmark_unavailability_is_always_stated_explicitly() -> None:
    content = build_report_content(_inputs())

    assert "Benchmarks: not available" in content.body
    assert "BTC/ETH/cash" in content.body


def test_an_active_non_reconciliation_breaker_is_warning_severity() -> None:
    breaker = Breaker(
        breaker_type=BreakerType.DAILY_LOSS, reason="daily loss exceeded", tripped_at=PERIOD_START
    )
    content = build_report_content(_inputs(active_breakers=(breaker,)))

    assert content.severity is ReportSeverity.WARNING
    assert "DAILY_LOSS: daily loss exceeded" in content.body
    assert "Reconciliation: healthy" in content.body


def test_an_active_reconciliation_breaker_is_critical_severity() -> None:
    breaker = Breaker(
        breaker_type=BreakerType.RECONCILIATION, reason="order mismatch", tripped_at=PERIOD_START
    )
    content = build_report_content(_inputs(active_breakers=(breaker,)))

    assert content.severity is ReportSeverity.CRITICAL
    assert "Reconciliation: DEGRADED -- order mismatch" in content.body


def test_a_stale_service_is_warning_severity_and_listed() -> None:
    heartbeats = (
        ServiceHeartbeat(service="api", age_seconds=5, stale=False),
        ServiceHeartbeat(service="worker", age_seconds=90, stale=True),
        ServiceHeartbeat(service="scheduler", age_seconds=None, stale=True),
        ServiceHeartbeat(service="research", age_seconds=5, stale=False),
    )
    content = build_report_content(_inputs(heartbeats=heartbeats))

    assert content.severity is ReportSeverity.WARNING
    assert "worker: STALE (90s ago)" in content.body
    assert "scheduler: STALE (no heartbeat received)" in content.body
    assert "api: HEALTHY (5s ago)" in content.body


def test_title_reflects_the_period_and_date() -> None:
    daily = build_report_content(_inputs(period=ReportPeriod.DAILY))
    weekly = build_report_content(_inputs(period=ReportPeriod.WEEKLY))

    assert daily.title == "Daily report -- 2026-01-08"
    assert weekly.title == "Weekly report -- 2026-01-08"
