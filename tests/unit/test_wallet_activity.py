from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "helius",
        "source_entity_id": None,
        "confidence": Decimal("0.9"),
        "evidence": "on-chain swap transaction",
        "verification_status": VerificationStatus.VERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_event(**overrides: Any) -> WalletActivityEvent:
    fields: dict[str, Any] = {
        "wallet_id": "solana:abc123",
        "chain": "solana",
        "transaction_hash": "tx-1",
        "token": "SOL",
        "action": OnChainActionType.SWAP,
        "amount": Decimal("10"),
        "value_usd": Decimal("1500"),
        "price": Decimal("150"),
        "liquidity_usd": Decimal("500000"),
        "occurred_at": NOW,
        "attribution": make_attribution(),
    }
    fields.update(overrides)
    return WalletActivityEvent(**fields)


def test_a_well_formed_event_is_accepted() -> None:
    event = make_event()
    assert event.action is OnChainActionType.SWAP
    assert event.amount == Decimal("10")


@pytest.mark.parametrize("field", ["wallet_id", "chain", "transaction_hash", "token"])
def test_required_identity_fields_cannot_be_empty(field: str) -> None:
    with pytest.raises(ValueError, match="required"):
        make_event(**{field: ""})


def test_amount_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        make_event(amount=Decimal("0"))
    with pytest.raises(ValueError, match="positive"):
        make_event(amount=Decimal("-1"))


@pytest.mark.parametrize("field", ["value_usd", "price", "liquidity_usd"])
def test_optional_monetary_fields_cannot_be_negative_when_present(field: str) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        make_event(**{field: Decimal("-1")})


def test_optional_monetary_fields_may_be_absent() -> None:
    event = make_event(value_usd=None, price=None, liquidity_usd=None)
    assert event.value_usd is None
    assert event.price is None
    assert event.liquidity_usd is None


def test_occurred_at_must_be_aware() -> None:
    with pytest.raises(ValueError, match="aware"):
        make_event(occurred_at=datetime(2026, 1, 1))
