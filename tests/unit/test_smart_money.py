from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.smart_money import (
    MIN_COMPLETED_TRADES,
    SmartMoneyScoreSnapshot,
    SmartMoneyStatus,
    score_smart_money,
)
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

NOW = datetime(2026, 1, 10, tzinfo=UTC)
WALLET_ID = "solana:abc123"


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "helius",
        "source_entity_id": None,
        "confidence": Decimal("0.9"),
        "evidence": "on-chain transaction",
        "verification_status": VerificationStatus.VERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_event(
    action: OnChainActionType,
    token: str,
    amount: Decimal,
    price: Decimal | None,
    occurred_at: datetime,
    transaction_hash: str,
) -> WalletActivityEvent:
    return WalletActivityEvent(
        wallet_id=WALLET_ID,
        chain="solana",
        transaction_hash=transaction_hash,
        token=token,
        action=action,
        amount=amount,
        value_usd=None if price is None else price * amount,
        price=price,
        liquidity_usd=None,
        occurred_at=occurred_at,
        attribution=make_attribution(observed_at=occurred_at),
    )


def _winning_round_trip(
    index: int, day_offset: int, token: str = "SOL"
) -> list[WalletActivityEvent]:
    buy_at = NOW - timedelta(days=day_offset, hours=1)
    sell_at = NOW - timedelta(days=day_offset)
    return [
        make_event(
            OnChainActionType.BUY, token, Decimal("1"), Decimal("100"), buy_at, f"buy-{index}"
        ),
        make_event(
            OnChainActionType.SELL, token, Decimal("1"), Decimal("150"), sell_at, f"sell-{index}"
        ),
    ]


def test_fewer_than_minimum_completed_trades_returns_insufficient_data() -> None:
    events: list[WalletActivityEvent] = []
    for i in range(MIN_COMPLETED_TRADES - 1):
        events.extend(_winning_round_trip(i, i))

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.INSUFFICIENT_DATA
    assert snapshot.score is None
    assert snapshot.trade_count == MIN_COMPLETED_TRADES - 1


def test_a_single_profitable_trade_is_never_enough_on_its_own() -> None:
    events = _winning_round_trip(0, 0)
    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.INSUFFICIENT_DATA


def test_enough_winning_trades_produces_a_scored_snapshot() -> None:
    events: list[WalletActivityEvent] = []
    for i in range(MIN_COMPLETED_TRADES):
        events.extend(_winning_round_trip(i, i))

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.SCORED
    assert snapshot.trade_count == MIN_COMPLETED_TRADES
    assert snapshot.win_rate == Decimal(1)
    assert snapshot.realized_pnl_usd == Decimal("50") * MIN_COMPLETED_TRADES
    assert snapshot.score is not None
    assert Decimal(0) <= snapshot.score <= Decimal(100)
    assert any("not evaluated" in reason for reason in snapshot.reasons)


def test_mixed_wins_and_losses_produce_a_partial_win_rate() -> None:
    events: list[WalletActivityEvent] = []
    for i in range(MIN_COMPLETED_TRADES):
        events.extend(_winning_round_trip(i, i))
    # One losing round trip added on top.
    events.append(
        make_event(
            OnChainActionType.BUY,
            "ETH",
            Decimal("1"),
            Decimal("200"),
            NOW - timedelta(days=10, hours=1),
            "buy-loss",
        )
    )
    events.append(
        make_event(
            OnChainActionType.SELL,
            "ETH",
            Decimal("1"),
            Decimal("150"),
            NOW - timedelta(days=10),
            "sell-loss",
        )
    )

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.SCORED
    assert snapshot.trade_count == MIN_COMPLETED_TRADES + 1
    assert snapshot.win_rate == Decimal(MIN_COMPLETED_TRADES) / Decimal(MIN_COMPLETED_TRADES + 1)


def test_a_sell_matches_the_earliest_open_lot_first_fifo() -> None:
    # Distinct token ("BONK") from the filler round trips (which default to "SOL") so the two
    # scenarios' FIFO lot queues never interact -- a real bug caught while writing this test:
    # reusing "SOL" for both silently mixed the two lot queues together.
    events = [
        make_event(
            OnChainActionType.BUY,
            "BONK",
            Decimal("1"),
            Decimal("100"),
            NOW - timedelta(days=5),
            "buy-1",
        ),
        make_event(
            OnChainActionType.BUY,
            "BONK",
            Decimal("1"),
            Decimal("120"),
            NOW - timedelta(days=4),
            "buy-2",
        ),
        make_event(
            OnChainActionType.SELL,
            "BONK",
            Decimal("1"),
            Decimal("150"),
            NOW - timedelta(days=3),
            "sell-1",
        ),
    ]
    for i in range(MIN_COMPLETED_TRADES - 1):
        events.extend(_winning_round_trip(100 + i, i))

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.SCORED
    # buy-2's lot is never sold, so only one BONK round trip completes: 150 - 100 = 50, matched
    # against the *first* lot (buy-1), never the second (which would have realized only 30).
    assert snapshot.trade_count == MIN_COMPLETED_TRADES  # 1 BONK trip + 4 filler SOL trips
    filler_pnl = Decimal("50") * (MIN_COMPLETED_TRADES - 1)
    fifo_pnl = Decimal("50")
    assert snapshot.realized_pnl_usd == filler_pnl + fifo_pnl


def test_events_with_no_price_are_ignored_not_guessed_at() -> None:
    events: list[WalletActivityEvent] = []
    for i in range(MIN_COMPLETED_TRADES):
        events.extend(_winning_round_trip(i, i))
    events.append(
        make_event(
            OnChainActionType.TRANSFER,
            "SOL",
            Decimal("1"),
            None,
            NOW - timedelta(days=1),
            "tx-noprice",
        )
    )

    snapshot = score_smart_money(WALLET_ID, events, NOW)
    assert snapshot.status is SmartMoneyStatus.SCORED
    assert snapshot.trade_count == MIN_COMPLETED_TRADES


def test_scored_snapshot_requires_a_score_in_range() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        SmartMoneyScoreSnapshot(
            wallet_id=WALLET_ID,
            version=1,
            status=SmartMoneyStatus.SCORED,
            score=None,
            trade_count=5,
            win_rate=Decimal("0.5"),
            realized_pnl_usd=Decimal("10"),
            wallet_age=timedelta(days=1),
            computed_at=NOW,
            reasons=("x",),
        )


def test_insufficient_data_snapshot_cannot_carry_a_score() -> None:
    with pytest.raises(ValueError, match="must not carry a score"):
        SmartMoneyScoreSnapshot(
            wallet_id=WALLET_ID,
            version=1,
            status=SmartMoneyStatus.INSUFFICIENT_DATA,
            score=Decimal("50"),
            trade_count=1,
            win_rate=None,
            realized_pnl_usd=None,
            wallet_age=None,
            computed_at=NOW,
            reasons=("x",),
        )


def test_snapshot_requires_at_least_one_reason() -> None:
    with pytest.raises(ValueError, match="reasons"):
        SmartMoneyScoreSnapshot(
            wallet_id=WALLET_ID,
            version=1,
            status=SmartMoneyStatus.INSUFFICIENT_DATA,
            score=None,
            trade_count=0,
            win_rate=None,
            realized_pnl_usd=None,
            wallet_age=None,
            computed_at=NOW,
            reasons=(),
        )
