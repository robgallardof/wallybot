from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.smart_money_cluster import (
    SmartMoneyClusterSignal,
    detect_smart_money_clusters,
)
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "helius",
        "source_entity_id": None,
        "confidence": Decimal("0.9"),
        "evidence": "on-chain buy",
        "verification_status": VerificationStatus.VERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_event(
    wallet_id: str,
    token: str,
    occurred_at: datetime,
    price: Decimal = Decimal("10"),
    amount: Decimal = Decimal("100"),
    action: OnChainActionType = OnChainActionType.BUY,
    chain: str = "solana",
    tx: str | None = None,
) -> WalletActivityEvent:
    return WalletActivityEvent(
        wallet_id=wallet_id,
        chain=chain,
        transaction_hash=tx or f"{wallet_id}-{occurred_at.isoformat()}",
        token=token,
        action=action,
        amount=amount,
        value_usd=price * amount,
        price=price,
        liquidity_usd=None,
        occurred_at=occurred_at,
        attribution=make_attribution(observed_at=occurred_at),
    )


def test_three_independent_wallets_buying_within_the_window_produce_a_signal() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=10))],
        "solana:c": [make_event("solana:c", "BONK", NOW + timedelta(minutes=20))],
    }
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet={},
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert len(signals) == 1
    signal = signals[0]
    assert signal.token == "BONK"
    assert signal.independent_wallet_count == 3
    assert set(signal.wallet_ids) == {"solana:a", "solana:b", "solana:c"}
    assert signal.total_value_usd == Decimal("3000")
    assert signal.independence_score == Decimal(1)
    assert any("not evaluated" in reason for reason in signal.reasons)


def test_two_wallets_never_meet_the_default_minimum() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=5))],
    }
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet={},
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert signals == ()


def test_wallets_outside_the_window_do_not_cluster() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=10))],
        "solana:c": [make_event("solana:c", "BONK", NOW + timedelta(hours=2))],
    }
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet={},
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert signals == ()


def test_wallets_controlled_by_the_same_entity_do_not_count_as_independent() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=5))],
        "solana:c": [make_event("solana:c", "BONK", NOW + timedelta(minutes=10))],
    }
    # a and b are the same entity -- only 2 independent participants (entity-1, wallet c), not 3.
    entity_by_wallet = {"solana:a": "entity-1", "solana:b": "entity-1", "solana:c": None}
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet=entity_by_wallet,
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert signals == ()


def test_a_fourth_wallet_from_the_same_entity_as_one_of_three_still_clusters() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=5))],
        "solana:c": [make_event("solana:c", "BONK", NOW + timedelta(minutes=10))],
        "solana:d": [make_event("solana:d", "BONK", NOW + timedelta(minutes=12))],
    }
    # a and d share an entity; b and c are independent of everyone -- still 3 independent groups.
    entity_by_wallet = {"solana:a": "entity-1", "solana:d": "entity-1"}
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet=entity_by_wallet,
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert len(signals) == 1
    assert signals[0].independent_wallet_count == 3
    assert signals[0].independence_score == Decimal(3) / Decimal(4)


def test_a_cluster_never_reuses_events_already_claimed_by_an_earlier_signal() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW)],
        "solana:b": [make_event("solana:b", "BONK", NOW + timedelta(minutes=5))],
        "solana:c": [make_event("solana:c", "BONK", NOW + timedelta(minutes=10))],
        "solana:d": [make_event("solana:d", "BONK", NOW + timedelta(minutes=40))],
        "solana:e": [make_event("solana:e", "BONK", NOW + timedelta(minutes=45))],
        "solana:f": [make_event("solana:f", "BONK", NOW + timedelta(minutes=50))],
    }
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet={},
        action=OnChainActionType.BUY,
        window=timedelta(minutes=15),
    )
    assert len(signals) == 2
    all_wallets = set()
    for signal in signals:
        assert not (all_wallets & set(signal.wallet_ids))
        all_wallets |= set(signal.wallet_ids)


def test_only_the_requested_action_is_considered() -> None:
    events_by_wallet = {
        "solana:a": [make_event("solana:a", "BONK", NOW, action=OnChainActionType.SELL)],
        "solana:b": [
            make_event(
                "solana:b", "BONK", NOW + timedelta(minutes=5), action=OnChainActionType.SELL
            )
        ],
        "solana:c": [
            make_event(
                "solana:c", "BONK", NOW + timedelta(minutes=10), action=OnChainActionType.SELL
            )
        ],
    }
    signals = detect_smart_money_clusters(
        events_by_wallet,
        entity_by_wallet={},
        action=OnChainActionType.BUY,
        window=timedelta(minutes=30),
    )
    assert signals == ()


def test_window_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window must be positive"):
        detect_smart_money_clusters(
            {}, entity_by_wallet={}, action=OnChainActionType.BUY, window=timedelta(0)
        )


def test_min_independent_wallets_must_be_at_least_two() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        detect_smart_money_clusters(
            {},
            entity_by_wallet={},
            action=OnChainActionType.BUY,
            window=timedelta(minutes=30),
            min_independent_wallets=1,
        )


def test_signal_rejects_fewer_than_two_wallets() -> None:
    with pytest.raises(ValueError, match="at least two wallets"):
        SmartMoneyClusterSignal(
            token="BONK",
            chain="solana",
            action=OnChainActionType.BUY,
            window_start=NOW,
            window_end=NOW,
            wallet_ids=("solana:a",),
            independent_wallet_count=1,
            total_value_usd=Decimal("100"),
            average_entry_price=Decimal("10"),
            independence_score=Decimal("1"),
            confidence=Decimal("1"),
            reasons=("x",),
        )
