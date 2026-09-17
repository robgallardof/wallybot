import asyncio
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pyotp
import pytest

from wallybot.application.price_consensus_job import (
    ProviderSource,
    _tiingo_source,
    run_price_consensus_tick,
)
from wallybot.domain.market import Candle, Instrument
from wallybot.domain.price_consensus import PriceConsensusStatus
from wallybot.exchanges.tiingo import BASE_URL
from wallybot.infrastructure.price_consensus_repository import PriceConsensusRepository
from wallybot.infrastructure.provider_reliability_repository import ProviderReliabilityRepository

pytestmark = pytest.mark.integration

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeCandleProvider:
    def __init__(self, price: str) -> None:
        self.price = price

    async def discover_instruments(self) -> list[Instrument]:
        raise NotImplementedError

    async def fetch_candles(self, instrument, timeframe, since, limit):
        return [
            Candle(
                instrument=instrument,
                timeframe="1m",
                open_time=NOW - timedelta(minutes=1),
                close_time=NOW,
                open=Decimal(self.price),
                high=Decimal(self.price),
                low=Decimal(self.price),
                close=Decimal(self.price),
                volume=Decimal("1"),
                source=instrument.venue,
                received_at=NOW,
            )
        ]

    async def fetch_snapshot(self, instrument):
        raise NotImplementedError


def enroll(client, settings) -> dict:
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    started = client.post("/api/auth/setup/start", json=body)
    assert started.status_code == 200, started.text
    enrollment = started.json()
    finished = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finished.status_code == 200, finished.text
    return finished.json()


async def tick(client, sources: list[ProviderSource]) -> None:
    await run_price_consensus_tick(
        client.app.state.sessions, client.app.state.auth.crypto, FixedClock(), sources, NOW, {}
    )


async def test_no_connection_means_kraken_only(client, settings) -> None:
    enroll(client, settings)

    await tick(client, [ProviderSource("kraken", FakeCandleProvider("100"))])

    # Filtered to this exact (fixed, past) `computed_at`: `client`'s real lifespan also runs its
    # own background `_price_consensus_loop` tick on a real clock (2026-09-17+), so `list_latest`
    # could otherwise pick up that unrelated row instead of the one this test just wrote.
    async with client.app.state.sessions() as db:
        kraken_history = await ProviderReliabilityRepository(db).history("kraken")
        tiingo_history = await ProviderReliabilityRepository(db).history("tiingo")
        btc_history = await PriceConsensusRepository(db).history("BTC/USD")

    assert any(row.computed_at == NOW for row in kraken_history)
    assert not any(row.computed_at == NOW for row in tiingo_history)
    assert any(
        row.computed_at == NOW and row.status is PriceConsensusStatus.INSUFFICIENT_DATA
        for row in btc_history
    )


async def test_a_ui_configured_tiingo_credential_is_picked_up_automatically(
    client, settings
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    added = client.post(
        "/api/connections",
        json={"provider": "TIINGO", "label": "primary", "mode": "READ_ONLY", "api_key": "fake-key"},
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 200, added.text

    # No mock: this exercises the real dynamic lookup added to close the exact gap the user
    # flagged -- a fake key against the real Tiingo API fails at the HTTP layer (401), which is
    # exactly what should happen and is recorded as an unsuccessful call, not silently ignored.
    await tick(client, [ProviderSource("kraken", FakeCandleProvider("100"))])

    async with client.app.state.sessions() as db:
        tiingo_history = await ProviderReliabilityRepository(db).history("tiingo")

    assert any(row.computed_at == NOW for row in tiingo_history)


async def test_tiingo_source_client_actually_targets_the_real_api(client, settings) -> None:
    # Regression test: a per-tick httpx.AsyncClient built without `base_url` raises
    # httpx.UnsupportedProtocol on every call -- a real bug found live (Tiingo recorded zero
    # calls at all, not even failed ones, because the request never left the process). Asserting
    # on `base_url` catches this deterministically, unlike asserting on latency/success, which
    # would depend on real network conditions.
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    added = client.post(
        "/api/connections",
        json={"provider": "TIINGO", "label": "primary", "mode": "READ_ONLY", "api_key": "fake-key"},
        headers={"X-CSRF-Token": csrf},
    )
    assert added.status_code == 200, added.text

    source, tiingo_client = await _tiingo_source(
        client.app.state.sessions, client.app.state.auth.crypto, FixedClock()
    )
    try:
        assert source is not None
        assert tiingo_client is not None
        assert str(tiingo_client.base_url) == BASE_URL
    finally:
        if tiingo_client is not None:
            await tiingo_client.aclose()
