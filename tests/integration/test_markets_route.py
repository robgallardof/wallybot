from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import partial

import pyotp
import pytest

from wallybot.application.market_overview import build_market_overview
from wallybot.data.quality import QualityPolicy
from wallybot.exchanges.fake import FakeExchange
from wallybot.market.universe import UniverseFilterConfig

pytestmark = pytest.mark.integration


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


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


def test_markets_route_requires_auth(client) -> None:
    assert client.get("/api/markets").status_code == 401


def test_markets_route_serves_the_market_overview_shape(client, settings) -> None:
    # The route is wired to KrakenExchange in production; swap in FakeExchange here so this
    # mandatory test never depends on external exchange availability, per TESTING.md.
    clock = FixedClock(datetime(2026, 1, 2, tzinfo=UTC))
    client.app.state.market_overview = partial(
        build_market_overview,
        provider=FakeExchange(clock=clock, seed=1),
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
    enroll(client, settings)

    response = client.get("/api/markets")
    assert response.status_code == 200
    body = response.json()
    assert body["as_of"]
    assert body["rows"]
    for row in body["rows"]:
        assert set(row) == {
            "id",
            "venue",
            "base",
            "quote",
            "bid",
            "ask",
            "spread_ratio",
            "quality_status",
            "quality_reasons",
            "eligible",
            "rejection_reasons",
            "score",
            "rank",
        }
        assert row["quality_status"] in {"PASS", "WARNING", "FAILURE"}
        if row["eligible"]:
            assert row["score"] is not None
            assert row["rank"] is not None
