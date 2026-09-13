from datetime import UTC, datetime, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.smart_money import MIN_COMPLETED_TRADES, SmartMoneyStatus, score_smart_money
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

NOW = datetime(2026, 1, 1, tzinfo=UTC)
WALLET_ID = "solana:abc123"


def _round_trip(index: int, entry_price: Decimal, exit_price: Decimal) -> list[WalletActivityEvent]:
    # Each round trip uses its own token, so lots from different round trips never share a FIFO
    # queue -- every round trip is independently exactly one completed trade by construction.
    token = f"TOKEN{index}"
    buy_at = NOW - timedelta(days=index + 1, hours=1)
    sell_at = NOW - timedelta(days=index)
    attribution = Attribution(
        source="helius",
        source_entity_id=None,
        confidence=Decimal("0.9"),
        evidence="on-chain transaction",
        verification_status=VerificationStatus.VERIFIED,
        observed_at=buy_at,
    )
    return [
        WalletActivityEvent(
            wallet_id=WALLET_ID,
            chain="solana",
            transaction_hash=f"buy-{index}",
            token=token,
            action=OnChainActionType.BUY,
            amount=Decimal("1"),
            value_usd=entry_price,
            price=entry_price,
            liquidity_usd=None,
            occurred_at=buy_at,
            attribution=attribution,
        ),
        WalletActivityEvent(
            wallet_id=WALLET_ID,
            chain="solana",
            transaction_hash=f"sell-{index}",
            token=token,
            action=OnChainActionType.SELL,
            amount=Decimal("1"),
            value_usd=exit_price,
            price=exit_price,
            liquidity_usd=None,
            occurred_at=sell_at,
            attribution=attribution,
        ),
    ]


_price = st.decimals(
    min_value="1", max_value="1000", places=2, allow_nan=False, allow_infinity=False
)


@given(prices=st.lists(st.tuples(_price, _price), min_size=0, max_size=15))
@settings(max_examples=200)
def test_score_is_always_bounded_and_status_matches_the_completed_trade_count(prices):
    events: list[WalletActivityEvent] = []
    for index, (entry, exit_price) in enumerate(prices):
        events.extend(_round_trip(index, entry, exit_price))

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.trade_count == len(prices)

    if len(prices) < MIN_COMPLETED_TRADES:
        assert snapshot.status is SmartMoneyStatus.INSUFFICIENT_DATA
        assert snapshot.score is None
    else:
        assert snapshot.status is SmartMoneyStatus.SCORED
        assert snapshot.score is not None
        assert Decimal(0) <= snapshot.score <= Decimal(100)
        assert snapshot.win_rate is not None
        assert Decimal(0) <= snapshot.win_rate <= Decimal(1)


@given(prices=st.lists(st.tuples(_price, _price), min_size=MIN_COMPLETED_TRADES, max_size=15))
@settings(max_examples=100)
def test_scoring_the_same_events_twice_is_deterministic(prices):
    events: list[WalletActivityEvent] = []
    for index, (entry, exit_price) in enumerate(prices):
        events.extend(_round_trip(index, entry, exit_price))

    first = score_smart_money(WALLET_ID, events, NOW)
    second = score_smart_money(WALLET_ID, events, NOW)
    assert first == second
