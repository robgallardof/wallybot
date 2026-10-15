"""Binance spot adapter using its public (unauthenticated) REST market-data endpoints.

Public endpoints only -- no API key and no trading credentials, exactly like `kraken.py`. Private
account and order calls live in `binance_private.py` behind their own reviewed capability.

Binance asset codes are used unchanged (BTC, ETH, USDT), so `base + quote` is always the venue
symbol. Only closed candles are returned: Binance includes the in-progress kline as its last row.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

import httpx

from wallybot.domain.clock import Clock
from wallybot.domain.market import Candle, Instrument, MarketSnapshot, MarketType

_BASE_URL = "https://api.binance.com"
_INTERVALS = {"1m": "1m", "5m": "5m", "1h": "1h", "1d": "1d"}
_STEPS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}
VENUE = "binance"


class BinanceTransport(Protocol):
    """Narrow public HTTP surface, swappable for recorded fixtures in tests."""

    async def get(self, path: str, params: dict[str, str]) -> Any: ...


class HttpxBinanceTransport:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(base_url=_BASE_URL, timeout=10.0)

    async def get(self, path: str, params: dict[str, str]) -> Any:
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()


# Curated liquid Binance USDT spot markets -- established coins plus a few high-volume memecoins.
# Shared by the market overview and the AI analyst; ingestion remains bounded to BTC and ETH.
CURATED_USDT_PAIRS = tuple(
    (base, "USDT")
    for base in (
        "BTC",
        "ETH",
        "SOL",
        "XRP",
        "ADA",
        "DOGE",
        "LTC",
        "DOT",
        "LINK",
        "AVAX",
        "BCH",
        "XLM",
        "UNI",
        "ATOM",
        "ETC",
        "FIL",
        "NEAR",
        "APT",
        "ARB",
        "TRX",
        "SHIB",
        "SUI",
        "OP",
        "BNB",
        "PEPE",
    )
)


def _filter(info: dict[str, Any], name: str) -> dict[str, Any]:
    for item in info["filters"]:
        if item["filterType"] == name:
            return item
    raise ValueError(f"Binance symbol is missing its {name} filter")


class BinanceExchange:
    def __init__(
        self,
        clock: Clock,
        symbols: tuple[tuple[str, str], ...] = (("BTC", "USDT"), ("ETH", "USDT")),
        transport: BinanceTransport | None = None,
    ) -> None:
        self.clock = clock
        self.symbols = symbols
        self.transport = transport or HttpxBinanceTransport()

    async def symbol_info(self, instrument: Instrument) -> dict[str, Any]:
        payload = await self.transport.get(
            "/api/v3/exchangeInfo", {"symbol": self.symbol(instrument)}
        )
        (info,) = payload["symbols"]
        if (
            info.get("symbol") != self.symbol(instrument)
            or info.get("baseAsset") != instrument.base
            or info.get("quoteAsset") != instrument.quote
            or info.get("status") != "TRADING"
            or info.get("isSpotTradingAllowed") is not True
        ):
            raise ValueError("Binance spot instrument is unavailable or mismatched")
        return info

    async def discover_instruments(self) -> list[Instrument]:
        names = ",".join(f'"{base}{quote}"' for base, quote in self.symbols)
        payload = await self.transport.get("/api/v3/exchangeInfo", {"symbols": f"[{names}]"})
        instruments = []
        requested = {base + quote for base, quote in self.symbols}
        seen: set[str] = set()
        for info in payload["symbols"]:
            if info.get("status") != "TRADING" or not info.get("isSpotTradingAllowed", False):
                continue
            name = info.get("symbol")
            if (
                name not in requested
                or name != info.get("baseAsset", "") + info.get("quoteAsset", "")
                or name in seen
            ):
                raise ValueError("Unexpected or duplicate Binance instrument")
            seen.add(name)
            lot = _filter(info, "LOT_SIZE")
            instruments.append(
                Instrument(
                    venue=VENUE,
                    market_type=MarketType.SPOT,
                    base=info["baseAsset"],
                    quote=info["quoteAsset"],
                    price_increment=Decimal(_filter(info, "PRICE_FILTER")["tickSize"]).normalize(),
                    quantity_increment=Decimal(lot["stepSize"]).normalize(),
                    min_quantity=Decimal(lot["minQty"]).normalize(),
                )
            )
        return instruments

    async def fetch_candles(
        self, instrument: Instrument, timeframe: str, since: datetime, limit: int
    ) -> list[Candle]:
        if timeframe not in _INTERVALS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        rows = await self.transport.get(
            "/api/v3/klines",
            {
                "symbol": self.symbol(instrument),
                "interval": _INTERVALS[timeframe],
                "startTime": str(int(since.timestamp() * 1000)),
                "limit": str(min(limit + 1, 1000)),
            },
        )
        now = self.clock.now()
        step = _STEPS[timeframe]
        candles = []
        for row in rows:
            open_time = datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC)
            close_time = open_time + step
            # Binance's last kline is still forming; never hand it to features as closed data.
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
                    volume=Decimal(row[5]),
                    source=VENUE,
                    received_at=now,
                )
            )
        return candles[:limit]

    async def fetch_snapshot(self, instrument: Instrument) -> MarketSnapshot:
        ticker = await self.transport.get(
            "/api/v3/ticker/bookTicker", {"symbol": self.symbol(instrument)}
        )
        return MarketSnapshot(
            instrument=instrument,
            bid=Decimal(ticker["bidPrice"]),
            ask=Decimal(ticker["askPrice"]),
            timestamp=self.clock.now(),
            source=VENUE,
        )

    async def fetch_depth(self, instrument: Instrument, limit: int = 100) -> dict[str, Any]:
        return await self.transport.get(
            "/api/v3/depth", {"symbol": self.symbol(instrument), "limit": str(limit)}
        )

    @staticmethod
    def symbol(instrument: Instrument) -> str:
        if instrument.venue != VENUE or instrument.market_type != MarketType.SPOT:
            raise ValueError("Binance public data requires a Binance spot instrument")
        return f"{instrument.base}{instrument.quote}"
