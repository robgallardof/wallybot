from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import psycopg
import pyotp
import pytest

from wallybot.application.backtest_orchestrator import BacktestOrchestrator
from wallybot.data.historical import HistoricalStore
from wallybot.data.historical_query import DEFAULT_QUERY_LIMITS
from wallybot.domain.market import Candle, Instrument, MarketType
from wallybot.exchanges.fake import FakeExchange
from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator

pytestmark = pytest.mark.integration

# Matches FakeExchange's own "fake"/BTC/USD instrument identity exactly -- the Parquet fixture
# below is written under that same venue/base/quote so read_candles finds it.
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
PRICES = ["100", "101", "102", "103", "104", "105", "104", "103", "102", "101", "100"]


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_series() -> list[Candle]:
    candles = []
    for i, price in enumerate(PRICES):
        open_time = START + timedelta(hours=i)
        candles.append(
            Candle(
                instrument=INSTRUMENT,
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                open=Decimal(price),
                high=Decimal(price),
                low=Decimal(price),
                close=Decimal(price),
                volume=Decimal("10"),
                source="fake",
                received_at=open_time + timedelta(hours=1),
            )
        )
    return candles


def write_fixture(root: Path) -> None:
    store = HistoricalStore(root, FixedClock(datetime(2026, 1, 2, tzinfo=UTC)), UuidIdGenerator())
    store.write_partition(make_series(), quality_status="PASS")


def enroll(client, settings):
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    result = client.post("/api/auth/setup/start", json=body)
    assert result.status_code == 200, result.text
    enrollment = result.json()
    finish = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finish.status_code == 200, finish.text
    return finish.json()


def wire_fake_orchestrator(client, data_root: Path) -> None:
    # The route is wired to KrakenExchange + the real Parquet volume in production; swap in
    # FakeExchange + a tmp data_root here so this mandatory test never depends on external
    # exchange availability, per TESTING.md.
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    client.app.state.backtest_orchestrator = BacktestOrchestrator(
        provider=FakeExchange(clock=clock, seed=1),
        data_root=data_root,
        resource_limits=DEFAULT_QUERY_LIMITS,
        clock=clock,
        id_generator=UuidIdGenerator(),
    )


def run_body(**overrides) -> dict:
    body = {
        "instrument_base": "BTC",
        "instrument_quote": "USD",
        "timeframe": "1h",
        "window_start": START.isoformat(),
        "window_end": (START + timedelta(hours=len(PRICES))).isoformat(),
        "feature_window": 3,
        "risk_off_threshold": "0.5",
        "starting_equity": "10000",
        "allocation_pct": "1",
        "fee_rate": "0",
        "slippage_pct": "0",
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def _reset_experiments_table(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute("TRUNCATE experiment_records CASCADE")
    yield


def test_backtest_routes_require_auth(client) -> None:
    assert client.get("/api/backtests").status_code == 401
    assert client.post("/api/backtests", json=run_body()).status_code == 401


def test_running_a_backtest_persists_and_is_visible_in_history(client, settings, tmp_path) -> None:
    write_fixture(tmp_path)
    wire_fake_orchestrator(client, tmp_path)
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post("/api/backtests", json=run_body(), headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trade_count"] == 1
    assert body["instrument_base"] == "BTC"
    assert body["bootstrap"] is None
    assert body["walk_forward"] is None

    history = client.get("/api/backtests")
    assert history.status_code == 200
    rows = history.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["experiment_id"] == body["experiment_id"]
    assert rows[0]["trade_count"] == 1


def test_running_a_backtest_with_walk_forward_windows_returns_per_window_results(
    client, settings, tmp_path
) -> None:
    write_fixture(tmp_path)
    wire_fake_orchestrator(client, tmp_path)
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post(
        "/api/backtests",
        json=run_body(walk_forward_windows=2),
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    windows = response.json()["walk_forward"]
    assert len(windows) == 2
    assert [w["index"] for w in windows] == [0, 1]


def test_running_a_backtest_requires_csrf(client, settings, tmp_path) -> None:
    write_fixture(tmp_path)
    wire_fake_orchestrator(client, tmp_path)
    enroll(client, settings)

    assert client.post("/api/backtests", json=run_body()).status_code == 403


def test_an_empty_dataset_is_reported_as_a_clear_422_not_a_fabricated_result(
    client, settings, tmp_path
) -> None:
    # No fixture written -- the data root exists but has no partitions for this instrument yet.
    wire_fake_orchestrator(client, tmp_path)
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.post("/api/backtests", json=run_body(), headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
    assert "at least" in response.json()["detail"]


def test_history_is_empty_before_any_backtest_has_run(client, settings) -> None:
    enroll(client, settings)
    response = client.get("/api/backtests")
    assert response.status_code == 200
    assert response.json()["rows"] == []
