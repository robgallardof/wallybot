"""Kraken adapter using its public (unauthenticated) REST market-data endpoints.

Public endpoints only -- no API key, no trading credentials, matching this port's "never
trading credentials" rule and ADR-004's "expose no withdrawal function". Authenticated/private
endpoints (balances, order submission) are explicitly out of scope until Phase 4 paper execution
actually needs them, at which point they get their own capability and their own review.

Kraken's own asset codes are passed through unrenamed (e.g. Bitcoin stays "XBT", not "BTC") so an
instrument's base/quote always round-trips back into a valid Kraken pair -- see `_altname`.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

import httpx

from wallybot.domain.clock import Clock
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType

_BASE_URL = "https://api.kraken.com"
_INTERVAL_MINUTES = {"1m": 1, "5m": 5, "1h": 60, "1d": 1440}


class KrakenTransport(Protocol):
    """The narrow HTTP surface KrakenExchange needs -- swappable for a fixture in tests, per
    TESTING.md: mandatory tests must not depend on external exchange availability."""

    async def get(self, path: str, params: dict[str, str]) -> dict: ...


class HttpxKrakenTransport:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0)

    async def get(self, path: str, params: dict[str, str]) -> dict:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise ValueError(f"Kraken API error for {path}: {payload['error']}")
        return payload


class KrakenExchange:
    def __init__(
        self,
        clock: Clock,
        pairs: tuple[str, ...] = ("XBTUSD", "ETHUSD"),
        transport: KrakenTransport | None = None,
    ) -> None:
        self.clock = clock
        self.pairs = pairs
        self.transport = transport or HttpxKrakenTransport()

    async def discover_instruments(self) -> list[Instrument]:
        payload = await self.transport.get("/0/public/AssetPairs", {"pair": ",".join(self.pairs)})
        instruments = []
        for info in payload["result"].values():
            base, _, quote = info["wsname"].partition("/")
            instruments.append(
                Instrument(
                    venue="kraken",
                    market_type=MarketType.SPOT,
                    base=base,
                    quote=quote,
                    price_increment=Decimal(info["tick_size"]),
                    quantity_increment=Decimal(1).scaleb(-info["lot_decimals"]),
                    min_quantity=Decimal(info["ordermin"]),
                )
            )
        return instruments

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        if timeframe not in _INTERVAL_MINUTES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        payload = await self.transport.get(
            "/0/public/OHLC",
            {
                "pair": self._altname(instrument),
                "interval": str(_INTERVAL_MINUTES[timeframe]),
                "since": str(int(since.timestamp())),
            },
        )
        rows, last_closed_ts = self._ohlc_rows_and_last_closed(payload)
        now = self.clock.now()
        step = timedelta(minutes=_INTERVAL_MINUTES[timeframe])
        candles = []
        for row in rows:
            # Kraken's OHLC response always includes the still-in-progress candle as its last
            # row; "last" is Kraken's own cursor for the last *closed* one. Treating the
            # in-progress candle as closed would hand the feature engine data from the future --
            # exactly what LookaheadError exists to catch -- so filter using Kraken's own
            # cursor first, then the wall clock as a second, independent check (clock skew).
            if row[0] > last_closed_ts:
                continue
            open_time = datetime.fromtimestamp(row[0], tz=UTC)
            close_time = open_time + step
            if close_time > now:
                continue
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=Decimal(row[1]),
                    high=Decimal(row[2]),
                    low=Decimal(row[3]),
                    close=Decimal(row[4]),
                    volume=Decimal(row[6]),
                    source="kraken",
                    received_at=now,
                )
            )
        return candles[:limit]

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        payload = await self.transport.get("/0/public/Ticker", {"pair": self._altname(instrument)})
        ticker = next(iter(payload["result"].values()))
        return MarketSnapshot(
            instrument=instrument,
            bid=Decimal(ticker["b"][0]),
            ask=Decimal(ticker["a"][0]),
            timestamp=self.clock.now(),
            source="kraken",
        )

    def _altname(self, instrument: Instrument) -> str:
        return f"{instrument.base}{instrument.quote}"

    def _ohlc_rows_and_last_closed(self, payload: dict) -> tuple[list, int]:
        result = payload["result"]
        if "last" not in result:
            raise ValueError("Kraken OHLC response is missing the 'last' closed-candle cursor")
        for key, value in result.items():
            if key != "last":
                return value, result["last"]
        raise ValueError("Kraken OHLC response is missing candle data")
