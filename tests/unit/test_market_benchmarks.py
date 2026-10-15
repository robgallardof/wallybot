from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.application.market_benchmarks import fetch_market_benchmarks
from wallybot.domain.benchmarks import compute_market_benchmarks
from wallybot.domain.market import Candle, Instrument, MarketType

START = datetime(2026, 10, 14, 0, tzinfo=UTC)
END = START + timedelta(hours=2)
NOW = END + timedelta(minutes=30)


def candle(base, price, close, quote="USDT", venue="binance"):
    value = Decimal(price)
    return Candle(
        Instrument(venue, MarketType.SPOT, base, quote),
        "1h",
        close - timedelta(hours=1),
        close,
        value,
        value,
        value,
        value,
        Decimal(1),
        venue,
        NOW,
    )


def evidence():
    return {
        "BTC": [candle("BTC", "100", START), candle("BTC", "110", END)],
        "ETH": [candle("ETH", "200", START), candle("ETH", "160", END)],
    }


def results(rows):
    return {row.name: row.return_pct for row in rows.returns}


def test_buy_and_hold_references_match_hand_calculated_example():
    result = compute_market_benchmarks("binance", "USDT", START, END, NOW, evidence())
    assert results(result) == {
        "BTC": Decimal("10"),
        "ETH": Decimal("-20"),
        "CASH": Decimal(0),
        "BTC_ETH_50_50": Decimal("-5"),
    }
    assert (result.start, result.end, result.currency, result.venue) == (
        START,
        END,
        "USDT",
        "binance",
    )


def test_missing_boundary_is_not_forward_filled_and_disables_passive_mix():
    rows = evidence()
    rows["BTC"][-1] = candle("BTC", "110", END - timedelta(hours=1))
    result = results(compute_market_benchmarks("binance", "USDT", START, END, NOW, rows))
    assert result["BTC"] is None and result["BTC_ETH_50_50"] is None
    assert result["ETH"] == Decimal("-20") and result["CASH"] == 0


@pytest.mark.parametrize(
    "failure", ["quote", "venue", "source", "duplicate", "forming", "future_receipt"]
)
def test_untrusted_or_incomplete_prices_cannot_become_a_reference(failure):
    rows = evidence()
    last = rows["BTC"][-1]
    if failure == "quote":
        rows["BTC"][-1] = replace(last, instrument=replace(last.instrument, quote="USD"))
    elif failure == "venue":
        rows["BTC"][-1] = replace(last, instrument=replace(last.instrument, venue="kraken"))
    elif failure == "source":
        rows["BTC"][-1] = replace(last, source="untrusted")
    elif failure == "future_receipt":
        rows["BTC"][-1] = replace(last, received_at=NOW + timedelta(days=1))
    elif failure == "duplicate":
        rows["BTC"].append(last)
    else:
        rows["BTC"][-1] = candle("BTC", "999", END + timedelta(hours=1))
    result = results(compute_market_benchmarks("binance", "USDT", START, END, NOW, rows))
    assert result["BTC"] is None and result["BTC_ETH_50_50"] is None


@pytest.mark.parametrize(
    "start,end",
    [
        (START, START),
        (START, NOW + timedelta(hours=1)),
        (START, END + timedelta(days=9)),
        (START + timedelta(minutes=1), END),
        (START.replace(tzinfo=None), END),
    ],
)
def test_invalid_windows_are_rejected(start, end):
    with pytest.raises(ValueError):
        compute_market_benchmarks("binance", "USDT", start, end, NOW, evidence())


def test_cash_reference_does_not_treat_usdt_as_usd():
    with pytest.raises(ValueError, match="venue/currency"):
        compute_market_benchmarks("binance", "USD", START, END, NOW, evidence())


class PublicPrices:
    def __init__(self, failed_asset=None):
        self.calls = []
        self.failed_asset = failed_asset

    async def fetch_candles(self, instrument, timeframe, since, limit):
        self.calls.append((instrument, timeframe, since, limit))
        if instrument.base == self.failed_asset:
            raise ConnectionError("do not expose provider details")
        return evidence()[instrument.base]


async def test_collection_uses_bounded_hourly_public_data_and_closed_end():
    provider = PublicPrices()
    result = await fetch_market_benchmarks(provider, "binance", "USDT", START, NOW)
    assert result is not None and result.end == END
    assert results(result)["BTC_ETH_50_50"] == Decimal("-5")
    assert len(provider.calls) == 2
    for instrument, timeframe, since, limit in provider.calls:
        assert instrument.venue == "binance" and instrument.quote == "USDT"
        assert (timeframe, since, limit) == ("1h", START - timedelta(hours=1), 4)


async def test_provider_failure_withholds_asset_and_mix_without_substitution():
    result = await fetch_market_benchmarks(PublicPrices("ETH"), "binance", "USDT", START, NOW)
    assert result is not None
    assert results(result)["BTC"] == Decimal("10")
    assert results(result)["ETH"] is None and results(result)["BTC_ETH_50_50"] is None


async def test_no_closed_interval_or_unsupported_currency_makes_no_request():
    provider = PublicPrices()
    assert await fetch_market_benchmarks(provider, "binance", "USDT", START, START) is None
    assert await fetch_market_benchmarks(provider, "binance", "USD", START, NOW) is None
    assert provider.calls == []


def test_legacy_kraken_reference_preserves_usd_and_xbt_identity():
    rows = {
        "BTC": [
            candle("XBT", "100", START, "USD", "kraken"),
            candle("XBT", "110", END, "USD", "kraken"),
        ],
        "ETH": [
            candle("ETH", "200", START, "USD", "kraken"),
            candle("ETH", "160", END, "USD", "kraken"),
        ],
    }
    result = compute_market_benchmarks("kraken", "USD", START, END, NOW, rows)
    assert results(result)["BTC_ETH_50_50"] == Decimal("-5")
    assert result.currency == "USD" and result.venue == "kraken"


def test_extreme_prices_withhold_reference_instead_of_breaking_the_report():
    rows = evidence()
    rows["BTC"] = [candle("BTC", "1e-999999", START), candle("BTC", "1e999999", END)]
    result = compute_market_benchmarks("binance", "USDT", START, END, NOW, rows)
    assert results(result)["BTC"] is None and results(result)["BTC_ETH_50_50"] is None
