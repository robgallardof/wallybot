import base64
from urllib.parse import parse_qs

import httpx
import pytest

from wallybot.exchanges.kraken_private import (
    REQUIRED_PERMISSIONS,
    KrakenPrivateError,
    SignedKrakenTransport,
    api_signature,
    spot_balances,
    validate_permissions,
)


def test_authentication_matches_documented_reference_vector():
    secret = (
        "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="
    )
    body = "nonce=1616492376594&ordertype=limit&pair=XBTUSD&price=37500&type=buy&volume=1.25"
    # Published golden value, not computed by the implementation under test.
    expected = (
        "4/dpxb3iT4tp/ZCVEwSnEsLxx0bqyhLpdfOpc6fn7OR8+UClSV5n9E6aSS8MPtnRfp32bAb0nmbRn6H8ndwLUQ=="
    )
    assert api_signature("/0/private/AddOrder", "1616492376594", body, secret) == expected


@pytest.mark.parametrize(
    "extra", ["withdraw-funds", "add-funds", "earn-funds", "add-withdraw-address", "unknown"]
)
def test_permissions_reject_funding_and_unknown_capabilities(extra):
    with pytest.raises(KrakenPrivateError):
        validate_permissions({"permissions": sorted(REQUIRED_PERMISSIONS | {extra})})


def test_missing_and_history_restricted_permissions_fail_closed():
    for info in (
        {},
        {"permissions": ["query-funds"]},
        {"permissions": sorted(REQUIRED_PERMISSIONS), "queryFrom": "1"},
    ):
        with pytest.raises(KrakenPrivateError):
            validate_permissions(info)
    validate_permissions({"permissions": sorted(REQUIRED_PERMISSIONS)})


def test_balances_exclude_holds_and_reject_credit():
    from decimal import Decimal

    assert spot_balances({"ZUSD": {"balance": "100", "hold_trade": "25"}}) == {
        "USD": (Decimal("100"), Decimal("75"))
    }
    for row in (
        {"balance": "NaN"},
        {"balance": "100", "credit": "1"},
        {"balance": "1", "hold_trade": "2"},
    ):
        with pytest.raises(KrakenPrivateError):
            spot_balances({"USD": row})


@pytest.mark.asyncio
async def test_transport_signs_exact_body_and_never_exposes_provider_payload():
    secret = base64.b64encode(b"test-secret").decode()
    requests = []

    async def nonce():
        return "1234"

    def respond(request):
        requests.append(request)
        assert parse_qs(request.content.decode()) == {"nonce": ["1234"]}
        assert request.headers["API-Sign"] == api_signature(
            request.url.path, "1234", request.content.decode(), secret
        )
        return httpx.Response(200, json={"error": ["sensitive-provider-payload"]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        transport = SignedKrakenTransport("test-key", secret, nonce, client)
        with pytest.raises(KrakenPrivateError) as error:
            await transport.call("GetApiKeyInfo", {})
        assert "sensitive-provider-payload" not in str(error.value)
        with pytest.raises(KrakenPrivateError):
            await transport.call("Withdraw", {})
    assert len(requests) == 1
