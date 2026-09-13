from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.smart_money_cluster import detect_smart_money_clusters
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

NOW = datetime(2026, 1, 1, tzinfo=UTC)
WINDOW = timedelta(minutes=30)


def _make_event(wallet_id: str, offset_minutes: int, price: Decimal) -> WalletActivityEvent:
    occurred_at = NOW + timedelta(minutes=offset_minutes)
    attribution = Attribution(
        source="helius",
        source_entity_id=None,
        confidence=Decimal("0.9"),
        evidence="on-chain buy",
        verification_status=VerificationStatus.VERIFIED,
        observed_at=occurred_at,
    )
    return WalletActivityEvent(
        wallet_id=wallet_id,
        chain="solana",
        transaction_hash=f"{wallet_id}-{offset_minutes}",
        token="BONK",
        action=OnChainActionType.BUY,
        amount=Decimal("100"),
        value_usd=price * Decimal("100"),
        price=price,
        liquidity_usd=None,
        occurred_at=occurred_at,
        attribution=attribution,
    )


_offsets = st.lists(st.integers(min_value=0, max_value=180), min_size=0, max_size=12, unique=True)
_price = st.decimals(
    min_value="0.01", max_value="1000", places=2, allow_nan=False, allow_infinity=False
)


@given(offsets=_offsets, prices=st.lists(_price, min_size=0, max_size=12))
@settings(max_examples=200)
def test_signals_always_respect_their_own_bounds_and_never_reuse_a_wallet(offsets, prices):
    paired = list(zip(offsets, prices, strict=False))
    events_by_wallet = {
        f"solana:w{index}": [_make_event(f"solana:w{index}", offset, price)]
        for index, (offset, price) in enumerate(paired)
    }

    signals = detect_smart_money_clusters(
        events_by_wallet, entity_by_wallet={}, action=OnChainActionType.BUY, window=WINDOW
    )

    seen_wallets: set[str] = set()
    for signal in signals:
        assert Decimal(0) <= signal.independence_score <= Decimal(1)
        assert Decimal(0) <= signal.confidence <= Decimal(1)
        assert signal.independent_wallet_count >= 3
        assert signal.independent_wallet_count <= len(signal.wallet_ids)
        assert signal.window_end >= signal.window_start
        assert signal.window_end - signal.window_start <= WINDOW
        assert signal.total_value_usd > 0
        assert signal.average_entry_price > 0
        assert not (seen_wallets & set(signal.wallet_ids))
        seen_wallets |= set(signal.wallet_ids)


@given(offsets=_offsets, prices=st.lists(_price, min_size=0, max_size=12))
@settings(max_examples=100)
def test_detection_is_deterministic(offsets, prices):
    paired = list(zip(offsets, prices, strict=False))
    events_by_wallet = {
        f"solana:w{index}": [_make_event(f"solana:w{index}", offset, price)]
        for index, (offset, price) in enumerate(paired)
    }

    first = detect_smart_money_clusters(
        events_by_wallet, entity_by_wallet={}, action=OnChainActionType.BUY, window=WINDOW
    )
    second = detect_smart_money_clusters(
        events_by_wallet, entity_by_wallet={}, action=OnChainActionType.BUY, window=WINDOW
    )
    assert first == second
