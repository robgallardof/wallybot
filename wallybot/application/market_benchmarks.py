"""Bounded public-data collection for informational market references. No private gateway."""

import asyncio
from datetime import UTC, datetime, timedelta

from wallybot.domain.benchmarks import MarketBenchmarks, compute_market_benchmarks
from wallybot.domain.market import Candle, Instrument, MarketDataProvider, MarketType


async def fetch_market_benchmarks(
    provider: MarketDataProvider,
    venue: str,
    currency: str,
    start: datetime,
    now: datetime,
) -> MarketBenchmarks | None:
    if any(t.tzinfo is None or t.utcoffset() != timedelta(0) for t in (start, now)):
        raise ValueError("Benchmark times must be aware UTC")
    end = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    if end <= start or end - start > timedelta(days=8):
        return None
    if (venue, currency) not in {("binance", "USDT"), ("kraken", "USD")}:
        return None
    limit = (end - start) // timedelta(hours=1) + 2

    async def fetch(base: str) -> tuple[str, list[Candle]]:
        instrument = Instrument(
            venue,
            MarketType.SPOT,
            "XBT" if venue == "kraken" and base == "BTC" else base,
            currency,
        )
        try:
            rows = await asyncio.wait_for(
                provider.fetch_candles(instrument, "1h", start - timedelta(hours=1), limit),
                timeout=5,
            )
        except (
            Exception
        ):  # Provider failure withholds only its reference; no retry or substitution.
            rows = []
        return base, rows

    evidence = dict(await asyncio.gather(fetch("BTC"), fetch("ETH")))
    return compute_market_benchmarks(venue, currency, start, end, now, evidence)
