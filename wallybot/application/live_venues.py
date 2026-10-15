"""Exchange-specific facts the real-account service needs, behind one narrow port.

`LiveTradingService` owns approval binding, limits, reconciliation and the ledger; a venue only
answers venue questions: are the key's permissions safe, what are the balances, what is the
minimum order, the fee and the visible book. No venue exposes a transfer or withdrawal method.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from wallybot.domain.execution import ExchangeGateway
from wallybot.domain.market import Instrument, MarketDataProvider
from wallybot.domain.order import OrderIntent
from wallybot.exchanges.binance import BinanceExchange
from wallybot.exchanges.binance_gateway import BinanceSpotGateway
from wallybot.exchanges.binance_private import (
    SUPPORTED_ASSETS as BINANCE_ASSETS,
)
from wallybot.exchanges.binance_private import (
    BinancePrivateError,
    taker_fee_rate,
    validate_restrictions,
)
from wallybot.exchanges.binance_private import (
    spot_balances as binance_balances,
)
from wallybot.exchanges.kraken_gateway import KrakenSpotGateway
from wallybot.exchanges.kraken_private import spot_balances as kraken_balances
from wallybot.exchanges.kraken_private import validate_permissions


class InvalidBookEvidence(Exception):
    pass


class LiveVenue(Protocol):
    name: str
    connection_provider: str
    cash: str
    assets: frozenset[str]
    unsupported_assets_message: str

    @property
    def market(self) -> MarketDataProvider: ...

    def gateway(
        self,
        transport: Any,
        load_intent: Callable[[str], Awaitable[OrderIntent]],
        now: Callable[[], datetime],
        authorize: Callable[[OrderIntent], Awaitable[bool]],
    ) -> ExchangeGateway: ...
    async def verify_key(self, transport: Any) -> None: ...
    async def has_open_orders(self, transport: Any) -> bool: ...
    async def balances(self, transport: Any) -> dict[str, tuple[Decimal, Decimal]]: ...
    async def minimum_notional(self, instrument: Instrument) -> Decimal: ...
    async def fee_rate(self, transport: Any, instrument: Instrument) -> Decimal: ...
    async def book(
        self, instrument: Instrument, buy: bool, now: datetime
    ) -> list[tuple[Decimal, Decimal]]: ...


def _level(price: Any, quantity: Any) -> tuple[Decimal, Decimal]:
    try:
        level_price, level_quantity = Decimal(str(price)), Decimal(str(quantity))
    except (InvalidOperation, ValueError):
        raise InvalidBookEvidence from None
    if (
        not level_price.is_finite()
        or level_price <= 0
        or not level_quantity.is_finite()
        or level_quantity < 0
    ):
        raise InvalidBookEvidence
    return level_price, level_quantity


class KrakenVenue:
    name = "kraken"
    connection_provider = "KRAKEN"
    cash = "USD"
    assets = frozenset({"USD", "XBT", "ETH"})
    unsupported_assets_message = "This adapter currently supports a USD/XBT/ETH spot account only"

    def __init__(self, market: Any) -> None:
        self.market = market

    def gateway(self, transport, load_intent, now, authorize) -> ExchangeGateway:
        return KrakenSpotGateway(transport, load_intent, now, authorize)

    async def verify_key(self, transport) -> None:
        validate_permissions(await transport.call("GetApiKeyInfo", {}))

    async def has_open_orders(self, transport) -> bool:
        return (await transport.call("OpenOrders", {})).get("open") != {}

    async def balances(self, transport) -> dict[str, tuple[Decimal, Decimal]]:
        return kraken_balances(await transport.call("BalanceEx", {}))

    async def minimum_notional(self, instrument: Instrument) -> Decimal:
        raw = await self.market.transport.get(
            "/0/public/AssetPairs", {"pair": instrument.base + instrument.quote}
        )
        return Decimal(str(next(iter(raw["result"].values()))["costmin"]))

    async def fee_rate(self, transport, instrument: Instrument) -> Decimal:
        data = await transport.call("TradeVolume", {"pair": instrument.base + instrument.quote})
        return max(Decimal(str(item["fee"])) for item in data["fees"].values()) / 100

    async def book(self, instrument, buy, now) -> list[tuple[Decimal, Decimal]]:
        depth = await self.market.transport.get(
            "/0/public/Depth", {"pair": instrument.base + instrument.quote, "count": "100"}
        )
        levels = []
        for level in next(iter(depth["result"].values()))["asks" if buy else "bids"]:
            timestamp = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(
                microseconds=int(Decimal(str(level[2])) * 1_000_000)
            )
            if timestamp > now:
                raise InvalidBookEvidence
            levels.append(_level(level[0], level[1]))
        return levels


class BinanceVenue:
    name = "binance"
    connection_provider = "BINANCE"
    cash = "USDT"
    assets = BINANCE_ASSETS
    unsupported_assets_message = (
        "This Binance adapter supports only USDT, BTC and ETH spot balances; move or convert "
        "other assets (including BNB) before activating"
    )

    def __init__(self, market: BinanceExchange) -> None:
        self.market = market

    def gateway(self, transport, load_intent, now, authorize) -> ExchangeGateway:
        return BinanceSpotGateway(transport, load_intent, now, authorize)

    async def verify_key(self, transport) -> None:
        validate_restrictions(await transport.call("GET", "/sapi/v1/account/apiRestrictions", {}))

    async def has_open_orders(self, transport) -> bool:
        opened = await transport.call("GET", "/api/v3/openOrders", {})
        if not isinstance(opened, list):
            raise BinancePrivateError("Invalid Binance response")
        return bool(opened)

    async def balances(self, transport) -> dict[str, tuple[Decimal, Decimal]]:
        return binance_balances(
            await transport.call("GET", "/api/v3/account", {"omitZeroBalances": "true"})
        )

    async def minimum_notional(self, instrument: Instrument) -> Decimal:
        info = await self.market.symbol_info(instrument)
        for item in info["filters"]:
            if item["filterType"] in {"NOTIONAL", "MIN_NOTIONAL"}:
                return Decimal(str(item["minNotional"]))
        raise BinancePrivateError("Binance minimum order size cannot be verified")

    async def fee_rate(self, transport, instrument: Instrument) -> Decimal:
        return taker_fee_rate(
            await transport.call(
                "GET",
                "/api/v3/account/commission",
                {"symbol": self.market.symbol(instrument)},
            )
        )

    async def book(self, instrument, buy, now) -> list[tuple[Decimal, Decimal]]:
        depth = await self.market.fetch_depth(instrument)
        side = depth.get("asks" if buy else "bids") if isinstance(depth, dict) else None
        if not isinstance(side, list):
            raise InvalidBookEvidence
        return [_level(level[0], level[1]) for level in side]
