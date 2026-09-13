from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.domain.whale_flow import detect_whale_transfers

NOW = datetime(2026, 1, 1, tzinfo=UTC)
THRESHOLD = Decimal("100000")


def _make_event(index: int, value_usd: Decimal | None) -> WalletActivityEvent:
    occurred_at = NOW + timedelta(minutes=index)
    return WalletActivityEvent(
        wallet_id=f"solana:w{index}",
        chain="solana",
        transaction_hash=f"tx{index}",
        token="SOL",
        action=OnChainActionType.TRANSFER,
        amount=Decimal("1"),
        value_usd=value_usd,
        price=value_usd,
        liquidity_usd=None,
        occurred_at=occurred_at,
        attribution=Attribution(
            source="helius",
            source_entity_id=None,
            confidence=Decimal("0.9"),
            evidence="on-chain transfer",
            verification_status=VerificationStatus.VERIFIED,
            observed_at=occurred_at,
        ),
    )


_maybe_value = st.one_of(
    st.none(),
    st.decimals(
        min_value="1", max_value="1000000", places=2, allow_nan=False, allow_infinity=False
    ),
)


@given(values=st.lists(_maybe_value, min_size=0, max_size=15))
@settings(max_examples=200)
def test_every_signal_meets_the_threshold_and_no_event_is_ever_dropped_from_the_count(values):
    events = [_make_event(index, value) for index, value in enumerate(values)]
    signals = detect_whale_transfers(events, THRESHOLD)

    expected_count = sum(1 for value in values if value is not None and value >= THRESHOLD)
    assert len(signals) == expected_count
    for signal in signals:
        assert signal.value_usd >= THRESHOLD


@given(values=st.lists(_maybe_value, min_size=0, max_size=15))
@settings(max_examples=100)
def test_detection_is_deterministic(values):
    events = [_make_event(index, value) for index, value in enumerate(values)]
    first = detect_whale_transfers(events, THRESHOLD)
    second = detect_whale_transfers(events, THRESHOLD)
    assert first == second
