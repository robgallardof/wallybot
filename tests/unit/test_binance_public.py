"""Binance public market data: precision from filters, closed candles only, venue routing."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from wallybot.domain.market import Instrument, MarketType
from wallybot.exchanges.binance import BinanceExchange
from wallybot.exchanges.venue_routing import VenueRoutedMarketData

NOW = datetime(2026, 10, 12, 9, 30, tzinfo=UTC)


class Clock:
    def now(self):
        return NOW


def symbol(base, status="TRADING"):
    return {
        "symbol": base + "USDT",
        "status": status,
        "baseAsset": base,
        "quoteAsset": "USDT",
        "isSpotTradingAllowed": True,
        "filters": [
            {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001000", "stepSize": "0.00001000"},
            {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
        ],
    }


class Transport:
    def __init__(self):
        self.calls = []

    async def get(self, path, params):
        self.calls.append((path, params))
        if path == "/api/v3/exchangeInfo":
            return {"symbols": [symbol("BTC"), symbol("ETH", status="BREAK")]}
        if path == "/api/v3/klines":
            start = datetime(2026, 10, 12, 7, tzinfo=UTC)
            return [
                [int((start + timedelta(hours=i)).timestamp() * 1000), "1", "2", "0.5", "1.5", "9"]
                for i in range(3)  # 07:00 and 08:00 closed; 09:00 still forming at 09:30
            ]
        if path == "/api/v3/ticker/bookTicker":
            return {"bidPrice": "100.00", "askPrice": "100.01"}
        raise AssertionError(path)


async def test_instruments_use_binance_filters_and_skip_halted_symbols():
    (btc,) = await BinanceExchange(Clock(), transport=Transport()).discover_instruments()
    assert (btc.venue, btc.base, btc.quote) == ("binance", "BTC", "USDT")
    assert btc.price_increment == Decimal("0.01")
    assert btc.quantity_increment == Decimal("0.00001")
    assert btc.min_quantity == Decimal("0.00001")


async def test_in_progress_kline_is_never_returned_as_closed_data():
    instrument = Instrument("binance", MarketType.SPOT, "BTC", "USDT")
    candles = await BinanceExchange(Clock(), transport=Transport()).fetch_candles(
        instrument, "1h", NOW - timedelta(hours=3), 3
    )
    assert [c.open_time.hour for c in candles] == [7, 8]
    assert all(c.close_time <= NOW and c.source == "binance" for c in candles)


async def test_marks_route_to_each_instruments_own_venue():
    binance = BinanceExchange(Clock(), transport=Transport())
    routed = VenueRoutedMarketData({"binance": binance})
    btc = Instrument("binance", MarketType.SPOT, "BTC", "USDT")
    snapshot = await routed.fetch_snapshot(btc)
    assert snapshot.source == "binance" and snapshot.bid == Decimal("100.00")
    with pytest.raises(LookupError):
        await routed.fetch_snapshot(Instrument("kraken", MarketType.SPOT, "XBT", "USD"))


async def test_public_adapter_rejects_another_venues_instrument_before_network():
    transport = Transport()
    provider = BinanceExchange(Clock(), transport=transport)
    with pytest.raises(ValueError, match="Binance spot"):
        await provider.fetch_snapshot(Instrument("kraken", MarketType.SPOT, "BTC", "USDT"))
    assert transport.calls == []


@pytest.mark.parametrize("base,status", [("ETH", "TRADING"), ("BTC", "BREAK")])
async def test_symbol_rules_reject_halted_or_mismatched_live_market(base, status):
    class WrongRules:
        async def get(self, path, params):
            return {"symbols": [symbol(base, status)]}

    provider = BinanceExchange(Clock(), transport=WrongRules())
    with pytest.raises(ValueError, match="unavailable or mismatched"):
        await provider.symbol_info(Instrument("binance", MarketType.SPOT, "BTC", "USDT"))
