from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.domain.whale_flow import WhaleTransferSignal, detect_whale_transfers

NOW = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLD = Decimal("100000")


def make_event(**overrides: Any) -> WalletActivityEvent:
    fields: dict[str, Any] = {
        "wallet_id": "solana:whale1",
        "chain": "solana",
        "transaction_hash": "tx1",
        "token": "SOL",
        "action": OnChainActionType.TRANSFER,
        "amount": Decimal("1000"),
        "value_usd": Decimal("150000"),
        "price": Decimal("150"),
        "liquidity_usd": None,
        "occurred_at": NOW,
        "attribution": Attribution(
            source="helius",
            source_entity_id=None,
            confidence=Decimal("0.9"),
            evidence="on-chain transfer",
            verification_status=VerificationStatus.VERIFIED,
            observed_at=NOW,
        ),
    }
    fields.update(overrides)
    return WalletActivityEvent(**fields)


def test_a_transfer_above_the_threshold_produces_a_signal() -> None:
    signals = detect_whale_transfers([make_event()], THRESHOLD)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.wallet_id == "solana:whale1"
    assert signal.value_usd == Decimal("150000")
    assert any("not evaluated" in reason for reason in signal.reasons)


def test_a_transfer_below_the_threshold_produces_no_signal() -> None:
    signals = detect_whale_transfers([make_event(value_usd=Decimal("50000"))], THRESHOLD)
    assert signals == ()


def test_a_transfer_exactly_at_the_threshold_produces_a_signal() -> None:
    signals = detect_whale_transfers([make_event(value_usd=THRESHOLD)], THRESHOLD)
    assert len(signals) == 1


def test_an_unpriced_event_is_skipped_not_treated_as_zero() -> None:
    signals = detect_whale_transfers([make_event(value_usd=None, price=None)], THRESHOLD)
    assert signals == ()


def test_multiple_events_each_above_threshold_all_produce_signals() -> None:
    events = [
        make_event(transaction_hash="tx1", value_usd=Decimal("200000")),
        make_event(transaction_hash="tx2", value_usd=Decimal("300000")),
        make_event(transaction_hash="tx3", value_usd=Decimal("50000")),
    ]
    signals = detect_whale_transfers(events, THRESHOLD)
    assert len(signals) == 2


def test_threshold_must_be_positive() -> None:
    with pytest.raises(ValueError, match="threshold_usd must be positive"):
        detect_whale_transfers([], Decimal("0"))


def test_signal_rejects_a_value_below_its_own_threshold() -> None:
    with pytest.raises(ValueError, match="must meet or exceed threshold_usd"):
        WhaleTransferSignal(
            wallet_id="solana:whale1",
            chain="solana",
            token="SOL",
            action=OnChainActionType.TRANSFER,
            amount=Decimal("100"),
            value_usd=Decimal("50"),
            threshold_usd=Decimal("100"),
            occurred_at=NOW,
            reasons=("x",),
        )
