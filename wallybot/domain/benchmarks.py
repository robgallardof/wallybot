"""Gross, nominal market references from exact closed hourly boundaries.

These are hypothetical buy-and-hold references, not account returns or executable signals.
USD and USDT are distinct. Missing boundaries are never interpolated or forward-filled.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, DecimalException

from wallybot.domain.market import Candle, MarketType


@dataclass(frozen=True)
class BenchmarkReturn:
    name: str
    return_pct: Decimal | None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class MarketBenchmarks:
    venue: str
    currency: str
    start: datetime
    end: datetime
    returns: tuple[BenchmarkReturn, ...]


def compute_market_benchmarks(
    venue: str,
    currency: str,
    start: datetime,
    end: datetime,
    as_of: datetime,
    candles: Mapping[str, Sequence[Candle]],
) -> MarketBenchmarks:
    for timestamp in (start, end, as_of):
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise ValueError("Benchmark timestamps must be aware UTC")
    if not start < end <= as_of or end - start > timedelta(days=8):
        raise ValueError("Benchmark window must be closed, positive and at most eight days")
    if any(t.minute or t.second or t.microsecond for t in (start, end)):
        raise ValueError("Benchmark boundaries must align to closed hours")
    if (venue, currency) not in {("binance", "USDT"), ("kraken", "USD")}:
        raise ValueError("Unsupported benchmark venue/currency")

    def asset_return(base: str) -> BenchmarkReturn:
        expected_base = "XBT" if venue == "kraken" and base == "BTC" else base
        prices: dict[datetime, Decimal] = {}
        for candle in candles.get(base, ()):
            if not start <= candle.close_time <= end:
                continue
            instrument = candle.instrument
            if (
                instrument.venue != venue
                or instrument.market_type != MarketType.SPOT
                or instrument.base != expected_base
                or instrument.quote != currency
                or candle.source != venue
                or candle.timeframe != "1h"
                or candle.close_time - candle.open_time != timedelta(hours=1)
                or candle.received_at > as_of + timedelta(minutes=1)
                or candle.close_time in prices
                or not candle.close.is_finite()
                or candle.close <= 0
            ):
                return BenchmarkReturn(base, None, "invalid_evidence")
            prices[candle.close_time] = candle.close
        if start not in prices or end not in prices:
            return BenchmarkReturn(base, None, "missing_boundary")
        try:
            change = (prices[end] / prices[start] - 1) * Decimal(100)
        except DecimalException:
            return BenchmarkReturn(base, None, "invalid_evidence")
        return BenchmarkReturn(base, change)

    btc, eth = asset_return("BTC"), asset_return("ETH")
    passive = (
        BenchmarkReturn("BTC_ETH_50_50", (btc.return_pct + eth.return_pct) / Decimal(2))
        if btc.return_pct is not None and eth.return_pct is not None
        else BenchmarkReturn("BTC_ETH_50_50", None, "missing_component")
    )
    return MarketBenchmarks(
        venue,
        currency,
        start,
        end,
        (btc, eth, BenchmarkReturn("CASH", Decimal(0)), passive),
    )
