"""Tiingo adapter for crypto market data -- the second `MarketDataProvider` this codebase has,
alongside `wallybot.exchanges.kraken.KrakenExchange`. Crypto only for now, matching Kraken's
existing scope; stocks/ETFs (Tiingo's `/tiingo/daily` and IEX-sourced intraday endpoints) are a
documented follow-up, not built here.

Contract verified against Tiingo's own docs and its official `tiingo-python` client (not
guessed): base URL `https://api.tiingo.com`, `Authorization: Token <key>` header, discovery via
`GET /tiingo/crypto`, candles via `GET /tiingo/crypto/prices`. A few details could not be verified
from public documentation and are called out below rather than assumed.

**Tiingo's crypto metadata reports no tick/lot size at all** -- unlike Kraken's `AssetPairs`,
there is no `price_increment`/`quantity_increment`/`min_quantity` anywhere in the response.
`Instrument`'s precision fields are optional precisely for this case (see its docstring): this
adapter returns them as `None`, never a guessed value. Anything that needs real precision (order
sizing, `wallybot.exchanges.fake.FakeExchange`, `wallybot.risk.deterministic_risk_engine`) already
fails closed on `None` rather than silently proceeding.

**No live quote/top-of-book endpoint**: Tiingo's `/tiingo/crypto/top` is deprecated, and no
replacement was found in the public docs. `fetch_snapshot` therefore always raises
`NotImplementedError` -- this adapter is not a drop-in replacement for `KrakenExchange` in any
composition that needs live bid/ask (e.g. `wallybot.application.market_overview`'s quality
filtering); it is usable for `discover_instruments`/`fetch_candles` only until that changes.

**Unverified, flagged rather than assumed**: the timezone of the `date` field in candle
responses (treated as UTC here, matching this codebase's UTC-only convention, but not confirmed
in Tiingo's docs), and whether `resampleFreq` accepts a daily value for crypto (this adapter
supports only "1m"/"5m"/"1h", the three frequencies the client library's own validation regex
confirms -- "1d" raises rather than guessing it works).

**Verified against the real API** (not guessed): `resampleFreq=1min` genuinely returns
minute-level bars up to the current minute -- Tiingo's crypto data is not end-of-day-only, despite
`endDate` being an *exclusive* boundary at that date's midnight (see `fetch_candles`'s `endDate`
computation) that looks, if missed, exactly like a data-freshness problem instead of an off-by-one
in the request.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from wallybot.domain.clock import Clock
from wallybot.domain.market import (
    TIMEFRAME_DURATIONS,
    Candle,
    Instrument,
    MarketSnapshot,
    MarketType,
)

_BASE_URL = "https://api.tiingo.com"
_RESAMPLE_FREQ = {"1m": "1min", "5m": "5min", "1h": "60min"}


class TiingoTransport(Protocol):
    """The narrow HTTP surface TiingoExchange needs -- swappable for a fixture in tests, per
    TESTING.md: mandatory tests must not depend on external exchange availability."""

    async def get(self, path: str, params: dict[str, str]) -> Any: ...


class HttpxTiingoTransport:
    def __init__(self, api_key: str, client: Any = None) -> None:
        import httpx

        self._api_key = api_key
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0)

    async def get(self, path: str, params: dict[str, str]) -> Any:
        response = await self._client.get(
            path, params=params, headers={"Authorization": f"Token {self._api_key}"}
        )
        response.raise_for_status()
        return response.json()


class TiingoExchange:
    def __init__(self, clock: Clock, transport: TiingoTransport) -> None:
        self.clock = clock
        self.transport = transport

    def _ticker(self, instrument: Instrument) -> str:
        return f"{instrument.base}{instrument.quote}".lower()

    async def discover_instruments(self) -> list[Instrument]:
        payload = await self.transport.get("/tiingo/crypto", {})
        instruments = []
        for entry in payload:
            base = str(entry["baseCurrency"]).upper()
            quote = str(entry["quoteCurrency"]).upper()
            instruments.append(
                Instrument(
                    venue="tiingo",
                    market_type=MarketType.SPOT,
                    base=base,
                    quote=quote,
                    # Tiingo's crypto metadata never reports tick/lot size -- never fabricated.
                    price_increment=None,
                    quantity_increment=None,
                    min_quantity=None,
                )
            )
        return instruments

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        if timeframe not in _RESAMPLE_FREQ:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        now = self.clock.now()
        step = TIMEFRAME_DURATIONS[timeframe]
        payload = await self.transport.get(
            "/tiingo/crypto/prices",
            {
                "tickers": self._ticker(instrument),
                "startDate": since.date().isoformat(),
                # One day past `now`'s date, not `now`'s date itself: verified against the real
                # API that `endDate` is an exclusive boundary at that date's midnight, so passing
                # today's date silently drops every row from today (the closer, more useful
                # data). `close_time > now` below still enforces no-lookahead regardless of this.
                "endDate": (now.date() + timedelta(days=1)).isoformat(),
                "resampleFreq": _RESAMPLE_FREQ[timeframe],
            },
        )
        rows = payload[0]["priceData"] if payload else []
        candles = []
        for row in rows:
            # `date` is the bucket's open time per Tiingo's OHLCV convention; close_time is
            # derived from the requested step, same as KrakenExchange does, since Tiingo's
            # response has no separate close-time field.
            open_time = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=UTC)
            if open_time < since:
                continue
            close_time = open_time + step
            if close_time > now:
                continue
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=close_time,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=Decimal(str(row["volume"])),
                    source="tiingo",
                    received_at=now,
                )
            )
        return candles[:limit]

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        raise NotImplementedError(
            "Tiingo has no live crypto quote endpoint (top-of-book is deprecated); "
            "fetch_snapshot is not available for this provider"
        )
