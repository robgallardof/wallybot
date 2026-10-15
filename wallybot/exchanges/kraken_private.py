"""Private Spot transport. Only account queries and order management are reachable.

No funding endpoints, margin, credentials in exceptions, or automatic HTTP retries.
The nonce supplier must serialize requests durably per API key in production.
"""

import base64
import hashlib
import hmac
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from wallybot.exchanges.private_errors import ExchangePrivateError

READ_METHODS = frozenset(
    {
        "GetApiKeyInfo",
        "BalanceEx",
        "OpenOrders",
        "ClosedOrders",
        "QueryOrders",
        "QueryTrades",
        "TradeVolume",
    }
)
ORDER_METHODS = frozenset({"AddOrder", "CancelOrder"})
REQUIRED_PERMISSIONS = frozenset(
    {"query-funds", "query-open-trades", "query-closed-trades", "modify-trades", "close-trades"}
)
ALLOWED_PERMISSIONS = REQUIRED_PERMISSIONS | {"query-ledger"}


class KrakenPrivateError(ExchangePrivateError):
    """Sanitized provider failure; raw response may contain account or key information."""


# Kraken error codes carry no key or account data. Map them to operator-actionable text and
# never echo the provider's raw response. First matching fragment wins.
_ERROR_EXPLANATIONS = (
    (
        "EAPI:Invalid key",
        "Kraken rejected the API key; check that it was copied completely and is not deleted",
    ),
    (
        "EAPI:Invalid signature",
        "Kraken rejected the signature; check that the private key (API secret) was copied "
        "completely",
    ),
    (
        "EAPI:Invalid nonce",
        "Kraken rejected the request sequence (nonce); use an API key dedicated to WallyBot",
    ),
    ("otp", "API keys with their own 2FA password are not supported; create one without it"),
    (
        "EGeneral:Permission denied",
        "The API key lacks a permission required for this operation",
    ),
    (
        "Rate limit exceeded",
        "Kraken is temporarily limiting this API key; wait a few minutes and retry",
    ),
    (
        "Temporary lockout",
        "Kraken is temporarily limiting this API key; wait a few minutes and retry",
    ),
    ("EService:", "Kraken is temporarily unavailable; retry later"),
    ("EOrder:Insufficient funds", "Kraken reports insufficient funds for this order"),
)


def explain_kraken_errors(errors: list[Any]) -> str:
    for fragment, explanation in _ERROR_EXPLANATIONS:
        if any(fragment.lower() in str(error).lower() for error in errors):
            return explanation
    return "Kraken rejected the private request"


class PrivateTransport(Protocol):
    async def call(self, method: str, params: dict[str, str]) -> dict[str, Any]: ...


def api_signature(path: str, nonce: str, body: str, secret: str) -> str:
    message = path.encode() + hashlib.sha256((nonce + body).encode()).digest()
    return base64.b64encode(
        hmac.new(base64.b64decode(secret, validate=True), message, hashlib.sha512).digest()
    ).decode()


def validate_permissions(info: dict[str, Any]) -> None:
    permissions = info.get("permissions")
    if not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions):
        raise KrakenPrivateError("Cannot verify API key permissions")
    granted = frozenset(permissions)
    if granted - ALLOWED_PERMISSIONS:
        raise KrakenPrivateError(
            "API key has excessive permissions; use only balance queries and spot order management"
        )
    if not REQUIRED_PERMISSIONS <= granted:
        raise KrakenPrivateError(
            "API key lacks required balance/order query, creation or cancellation permissions"
        )
    # Restricted history cannot establish complete reconciliation.
    if str(info.get("queryFrom", "0")) != "0" or str(info.get("queryTo", "0")) != "0":
        raise KrakenPrivateError("API key history restrictions prevent complete reconciliation")


class SignedKrakenTransport:
    def __init__(
        self,
        key: str,
        secret: str,
        next_nonce: Callable[[], Awaitable[str]],
        client: httpx.AsyncClient,
    ) -> None:
        self._key = key
        self._secret = secret
        self._next_nonce = next_nonce
        self._client = client

    async def call(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        if method not in READ_METHODS | ORDER_METHODS:
            raise KrakenPrivateError("Unsupported private operation")
        nonce = await self._next_nonce()
        path = f"/0/private/{method}"
        body = urlencode({**params, "nonce": nonce})
        try:
            signature = api_signature(path, nonce, body, self._secret)
        except ValueError:
            raise KrakenPrivateError(
                "The API secret is not in Kraken's format; paste the private key exactly"
            ) from None
        try:
            response = await self._client.post(
                "https://api.kraken.com" + path,
                content=body,
                headers={
                    "API-Key": self._key,
                    "API-Sign": signature,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            raise KrakenPrivateError(
                "Kraken could not be reached; check the connection and retry. An order's "
                "outcome may be unknown until reconciliation"
            ) from None
        if not isinstance(payload, dict) or not isinstance(payload.get("error"), list):
            raise KrakenPrivateError("Invalid Kraken response")
        if payload["error"]:
            raise KrakenPrivateError(explain_kraken_errors(payload["error"]))
        result = payload.get("result")
        if not isinstance(result, dict):
            raise KrakenPrivateError("Invalid Kraken result")
        return result


def spot_balances(result: dict[str, Any]) -> dict[str, tuple[Decimal, Decimal]]:
    """Total and available, excluding credit. Preserve unknown assets for valuation checks."""
    aliases = {"ZUSD": "USD", "XXBT": "XBT", "XETH": "ETH", "ZEUR": "EUR"}
    balances = {}
    for asset, item in result.items():
        if not isinstance(item, dict):
            raise KrakenPrivateError("Invalid balance response")
        total = Decimal(str(item["balance"]))
        credit = Decimal(str(item.get("credit", "0")))
        used = Decimal(str(item.get("credit_used", "0")))
        held = Decimal(str(item.get("hold_trade", "0")))
        if (
            not all(v.is_finite() and v >= 0 for v in (total, credit, used, held))
            or credit
            or used
            or held > total
        ):
            raise KrakenPrivateError(
                "Credit or invalid balances are not eligible for spot execution"
            )
        name = aliases.get(asset, asset)
        if name in balances:
            raise KrakenPrivateError("Ambiguous asset balance")
        balances[name] = (total, total - held)
    return balances
