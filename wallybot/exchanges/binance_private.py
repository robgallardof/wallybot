"""Binance spot private transport. Only account queries and spot order management are reachable.

No wallet, transfer, margin, futures or withdrawal endpoint exists in the allowlist below, and
exceptions never carry keys, signatures or raw provider payloads. Requests are HMAC-SHA256 signed
with a millisecond timestamp; Binance has no nonce, so no cross-process sequencing is needed.
"""

import hashlib
import hmac
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from wallybot.exchanges.binance import CURATED_USDT_PAIRS
from wallybot.exchanges.private_errors import ExchangePrivateError, TransientExchangeError

ALLOWED_CALLS = frozenset(
    {
        ("GET", "/sapi/v1/account/apiRestrictions"),
        ("GET", "/api/v3/account"),
        ("GET", "/api/v3/account/commission"),
        ("GET", "/api/v3/openOrders"),
        ("GET", "/api/v3/order"),
        ("GET", "/api/v3/myTrades"),
        ("POST", "/api/v3/order"),
        ("DELETE", "/api/v3/order"),
    }
)
# Every capability beyond reading and spot trading must be off. Withdrawals are checked even
# though no withdrawal endpoint is reachable: a leaked key must be useless for moving funds.
FORBIDDEN_PERMISSIONS = (
    "enableWithdrawals",
    "enableInternalTransfer",
    "permitsUniversalTransfer",
    "enableMargin",
    "enableFutures",
    "enableVanillaOptions",
    "enablePortfolioMarginTrading",
    "enableFixApiTrade",
)
# Spot assets the real account may hold: cash plus every curated pair's base. BNB stays out
# because Binance can charge fees in BNB, which would desynchronise the ledger.
SUPPORTED_ASSETS = frozenset({"USDT"}) | frozenset(
    base for base, quote in CURATED_USDT_PAIRS if quote == "USDT" and base != "BNB"
)


class BinancePrivateError(ExchangePrivateError):
    """Sanitized Binance failure; messages are safe to show the operator."""


class BinanceTransientError(BinancePrivateError, TransientExchangeError):
    """Binance failure that a later attempt is expected to clear."""


class BinanceOrderNotFound(BinancePrivateError):
    """Binance reports no order for the requested client identity (code -2013)."""


class BinancePrivateTransport(Protocol):
    async def call(self, method: str, path: str, params: dict[str, str]) -> Any: ...


_TRANSIENT_CODES = frozenset({-1003, -1021})
_ERROR_EXPLANATIONS = {
    -1003: "Binance is temporarily limiting requests; wait a few minutes and retry",
    -1013: "The order does not meet Binance's price or quantity rules",
    -1021: (
        "Binance rejected the request timestamp (clock offset or a slow network); the clock "
        "was resynchronized and the request will be retried"
    ),
    -1022: "Binance rejected the signature; check that the Secret Key was copied completely",
    -2008: "Binance does not recognize this API key; copy the API Key again or create a new one",
    -2014: "Binance rejected the API key format; copy the API Key again completely",
    -2015: (
        "Binance rejected the API key, its IP restriction or its permissions; check the key, "
        "allow this computer's public IP and enable spot trading"
    ),
}


def explain_binance_error(status: int, payload: Any) -> BinancePrivateError:
    code = payload.get("code") if isinstance(payload, dict) else None
    message = str(payload.get("msg", "")) if isinstance(payload, dict) else ""
    if code == -2013:
        return BinanceOrderNotFound("Binance has no order with this identity")
    if code == -2010 and "insufficient balance" in message.lower():
        return BinancePrivateError("Binance reports insufficient funds for this order")
    if code in _TRANSIENT_CODES:
        return BinanceTransientError(_ERROR_EXPLANATIONS[code])
    if code in _ERROR_EXPLANATIONS:
        return BinancePrivateError(_ERROR_EXPLANATIONS[code])
    if status in {418, 429}:
        return BinanceTransientError(_ERROR_EXPLANATIONS[-1003])
    if status == 451:
        return BinancePrivateError("Binance is not available from this location")
    return BinancePrivateError("Binance rejected the private request")


_UNREACHABLE = (
    "Binance could not be reached; check the connection and retry. An order's outcome may be "
    "unknown until reconciliation"
)
_UNAVAILABLE = (
    "Binance is temporarily unavailable; an order's outcome may be unknown until reconciliation"
)
# Every reason a BinanceTransientError can latch LIVE with, so the monitor can re-arm by itself
# once Binance answers again. Includes the pre-2c495a2 -1021 wording still stored in old blocks.
TRANSIENT_REASONS = frozenset(
    {
        *(_ERROR_EXPLANATIONS[code] for code in _TRANSIENT_CODES),
        _UNREACHABLE,
        _UNAVAILABLE,
        "This computer's clock is out of sync with Binance; enable automatic time "
        "synchronization in Windows and retry",
    }
)
# Reasons the monitor may clear by itself after a fully healthy sync. A rejected key/IP (-2015)
# blocks at once, but once Binance accepts the key again (and verify_key confirmed its
# restrictions, the ledger matches and no order is open) there is nothing left to review.
RECOVERABLE_REASONS = TRANSIENT_REASONS | {_ERROR_EXPLANATIONS[-2015]}

_SERVER_OFFSET: dict[str, float] = {}


def sign(query: str, secret: str) -> str:
    return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()


class SignedBinanceTransport:
    def __init__(
        self,
        key: str,
        secret: str,
        client: httpx.AsyncClient,
        clock_ms: Callable[[], int] | None = None,
        base_url: str = "https://api.binance.com",
    ) -> None:
        self._key = key
        self._secret = secret
        self._client = client
        self._clock_ms = clock_ms
        self._base_url = base_url

    async def _timestamp(self) -> int:
        """Binance rejects requests >5s off its clock; container clocks drift after host sleep."""
        if self._clock_ms is not None:
            return self._clock_ms()
        now = time.monotonic()
        if _SERVER_OFFSET.get("checked", -1e9) < now - 60:
            try:
                started = time.time_ns() // 1_000_000
                response = await self._client.get(f"{self._base_url}/api/v3/time", timeout=5)
                finished = time.time_ns() // 1_000_000
                server = int(response.json()["serverTime"])
                _SERVER_OFFSET["offset"] = server - (started + finished) // 2
                _SERVER_OFFSET["checked"] = now
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                pass  # Fall back to the local clock; Binance explains a skew as -1021.
        return time.time_ns() // 1_000_000 + int(_SERVER_OFFSET.get("offset", 0))

    async def call(self, method: str, path: str, params: dict[str, str]) -> Any:
        if (method, path) not in ALLOWED_CALLS:
            raise BinancePrivateError("Unsupported private operation")
        try:
            return await self._send(method, path, params)
        except BinanceTransientError as exc:
            # -1021 is rejected before Binance processes anything, so one retry is safe even for
            # orders; the server offset is re-measured first.
            if exc.args[0] != _ERROR_EXPLANATIONS[-1021] or self._clock_ms is not None:
                raise
            _SERVER_OFFSET.pop("checked", None)
            return await self._send(method, path, params)

    async def _send(self, method: str, path: str, params: dict[str, str]) -> Any:
        timestamp = str(await self._timestamp())
        query = urlencode({**params, "recvWindow": "5000", "timestamp": timestamp})
        url = f"{self._base_url}{path}?{query}&signature={sign(query, self._secret)}"
        try:
            response = await self._client.request(
                method,
                url,
                headers={"X-MBX-APIKEY": self._key},
                timeout=10,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise BinanceTransientError(_UNREACHABLE) from None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 500:
            raise BinanceTransientError(_UNAVAILABLE)
        if response.status_code >= 400:
            raise explain_binance_error(response.status_code, payload)
        if payload is None:
            raise BinancePrivateError("Invalid Binance response")
        return payload


def validate_restrictions(info: Any) -> None:
    if not isinstance(info, dict) or not isinstance(info.get("enableWithdrawals"), bool):
        raise BinancePrivateError("Cannot verify API key permissions")
    enabled = [name for name in FORBIDDEN_PERMISSIONS if info.get(name, False) is not False]
    if enabled:
        raise BinancePrivateError(
            "Binance API key has excessive permissions; enable only reading and spot trading"
        )
    if info.get("enableReading") is not True or info.get("enableSpotAndMarginTrading") is not True:
        raise BinancePrivateError("Binance API key needs reading and spot trading permissions")
    if info.get("ipRestrict") is not True:
        raise BinancePrivateError(
            "Restrict the Binance API key to trusted IPs (this computer's public IP)"
        )


def _amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BinancePrivateError("Invalid balance response") from None
    if not amount.is_finite() or amount < 0:
        raise BinancePrivateError("Invalid balance response")
    return amount


def spot_balances(account: Any) -> dict[str, tuple[Decimal, Decimal]]:
    """Total and available spot balances; non-zero assets are preserved for valuation checks."""
    if (
        not isinstance(account, dict)
        or account.get("accountType") != "SPOT"
        or account.get("canTrade") is not True
        or not isinstance(account.get("balances"), list)
    ):
        raise BinancePrivateError("The Binance account cannot trade spot right now")
    balances = {}
    for item in account["balances"]:
        if not isinstance(item, dict) or not isinstance(item.get("asset"), str):
            raise BinancePrivateError("Invalid balance response")
        free, locked = _amount(item.get("free")), _amount(item.get("locked"))
        if not free and not locked:
            continue
        if item["asset"] in balances:
            raise BinancePrivateError("Ambiguous asset balance")
        balances[item["asset"]] = (free + locked, free)
    return balances


@dataclass(frozen=True)
class SpotTrade:
    """One executed spot trade, shaped like a ledger fill so open_positions() can lot it."""

    base: str
    side: str
    quantity: Decimal
    price: Decimal
    filled_at: datetime


def spot_trades(trades: Any, base: str) -> list[SpotTrade]:
    """Account trades of one pair, oldest first; a base-asset commission shrinks what a buy got."""
    if not isinstance(trades, list):
        raise BinancePrivateError("Invalid trade history response")
    parsed = []
    for item in trades:
        if not isinstance(item, dict) or not isinstance(item.get("isBuyer"), bool):
            raise BinancePrivateError("Invalid trade history response")
        quantity = _amount(item.get("qty"))
        if item["isBuyer"] and item.get("commissionAsset") == base:
            quantity -= _amount(item.get("commission"))
        parsed.append(
            SpotTrade(
                base,
                "BUY" if item["isBuyer"] else "SELL",
                quantity,
                _amount(item.get("price")),
                datetime.fromtimestamp(int(item.get("time", 0)) / 1000, tz=UTC),
            )
        )
    return sorted(parsed, key=lambda trade: trade.filled_at)


def taker_fee_rate(commission: Any) -> Decimal:
    """Conservative taker rate: standard + special + tax, ignoring any BNB discount."""
    try:
        rate = sum(
            (
                Decimal(str(commission[group]["taker"]))
                + max(
                    Decimal(str(commission[group]["buyer"])),
                    Decimal(str(commission[group]["seller"])),
                )
                for group in ("standardCommission", "specialCommission", "taxCommission")
                if group in commission
            ),
            Decimal(0),
        )
    except (KeyError, TypeError, InvalidOperation, ValueError):
        raise BinancePrivateError("Trading fee cannot be verified") from None
    if (
        "standardCommission" not in commission
        or not rate.is_finite()
        or not Decimal(0) <= rate <= Decimal("0.10")
    ):
        raise BinancePrivateError("Trading fee cannot be verified")
    return rate
