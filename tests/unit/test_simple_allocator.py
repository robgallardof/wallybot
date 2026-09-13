from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.aggregation import AggregatedSignal
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.portfolio import Bucket, PortfolioPolicy, PortfolioState
from wallybot.domain.strategy import Action
from wallybot.portfolio.simple_allocator import SimplePortfolioAllocator

INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
AS_OF = datetime(2026, 1, 1, tzinfo=UTC)

POLICY = PortfolioPolicy(
    version=1,
    bucket_targets={
        Bucket.CORE: Decimal("0.70"),
        Bucket.GROWTH: Decimal("0.20"),
        Bucket.SPECULATIVE: Decimal("0.10"),
    },
    speculative_operating_max=Decimal("0.10"),
    speculative_absolute_max=Decimal("0.15"),
    single_speculative_asset_max=Decimal("0.03"),
    max_open_positions=1,
)


def make_signal(action: Action, confidence: str) -> AggregatedSignal:
    return AggregatedSignal(
        instrument=INSTRUMENT,
        action=action,
        confidence=Decimal(confidence),
        version=1,
        as_of=AS_OF,
        contributing_signals=(),
        reason="test",
    )


def make_state(**overrides) -> PortfolioState:
    fields = {
        "equity": Decimal("10000"),
        "bucket_exposure": {},
        "asset_exposure": {},
        "open_positions": 0,
    }
    fields.update(overrides)
    return PortfolioState(**fields)


ALLOCATOR = SimplePortfolioAllocator()


def test_hold_signal_is_rejected():
    proposal = ALLOCATOR.propose(
        make_signal(Action.HOLD, "0"), Bucket.CORE, make_state(), POLICY, AS_OF
    )
    assert proposal.approved is False
    assert proposal.reasons == ("signal is HOLD",)


def test_sell_signal_raises_without_position_data():
    with pytest.raises(ValueError):
        ALLOCATOR.propose(make_signal(Action.SELL, "1"), Bucket.CORE, make_state(), POLICY, AS_OF)


def test_max_open_positions_reached_is_rejected():
    state = make_state(open_positions=1)
    proposal = ALLOCATOR.propose(make_signal(Action.BUY, "0.5"), Bucket.CORE, state, POLICY, AS_OF)
    assert proposal.approved is False
    assert proposal.reasons == ("max open positions reached",)


def test_core_bucket_with_room_is_approved():
    proposal = ALLOCATOR.propose(
        make_signal(Action.BUY, "0.5"), Bucket.CORE, make_state(), POLICY, AS_OF
    )
    assert proposal.approved is True
    # target = 7000, room = 7000, proposed = 7000 * 0.5 = 3500
    assert proposal.proposed_notional == Decimal("3500")


def test_core_bucket_fully_used_is_rejected():
    state = make_state(bucket_exposure={Bucket.CORE: Decimal("7000")})
    proposal = ALLOCATOR.propose(make_signal(Action.BUY, "0.5"), Bucket.CORE, state, POLICY, AS_OF)
    assert proposal.approved is False
    assert proposal.reasons == ("bucket ceiling already reached",)


def test_speculative_capped_by_single_asset_ceiling():
    proposal = ALLOCATOR.propose(
        make_signal(Action.BUY, "1"), Bucket.SPECULATIVE, make_state(), POLICY, AS_OF
    )
    assert proposal.approved is True
    # bucket room 1000, operating room 1000, single-asset cap 300 -> capped at 300
    assert proposal.proposed_notional == Decimal("300")


def test_speculative_operating_ceiling_reached_when_bucket_target_is_wider():
    wide_policy = PortfolioPolicy(
        version=1,
        bucket_targets={
            Bucket.CORE: Decimal("0.65"),
            Bucket.GROWTH: Decimal("0.20"),
            Bucket.SPECULATIVE: Decimal("0.15"),
        },
        speculative_operating_max=Decimal("0.10"),
        speculative_absolute_max=Decimal("0.15"),
        single_speculative_asset_max=Decimal("0.03"),
        max_open_positions=1,
    )
    state = make_state(bucket_exposure={Bucket.SPECULATIVE: Decimal("1000")})
    proposal = ALLOCATOR.propose(
        make_signal(Action.BUY, "1"), Bucket.SPECULATIVE, state, wide_policy, AS_OF
    )
    assert proposal.approved is False
    assert proposal.reasons == ("speculative operating ceiling reached",)


def test_single_speculative_asset_ceiling_reached():
    state = make_state(asset_exposure={INSTRUMENT.id: Decimal("300")})
    proposal = ALLOCATOR.propose(
        make_signal(Action.BUY, "1"), Bucket.SPECULATIVE, state, POLICY, AS_OF
    )
    assert proposal.approved is False
    assert proposal.reasons == ("single speculative asset ceiling reached",)
