from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import Side
from wallybot.domain.portfolio import (
    AllocationProposal,
    Bucket,
    PortfolioPolicy,
    PortfolioState,
)

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

VALID_TARGETS = {
    Bucket.CORE: Decimal("0.70"),
    Bucket.GROWTH: Decimal("0.20"),
    Bucket.SPECULATIVE: Decimal("0.10"),
}


def make_policy(**overrides) -> PortfolioPolicy:
    fields = {
        "version": 1,
        "bucket_targets": VALID_TARGETS,
        "speculative_operating_max": Decimal("0.10"),
        "speculative_absolute_max": Decimal("0.15"),
        "single_speculative_asset_max": Decimal("0.03"),
        "max_open_positions": 1,
    }
    fields.update(overrides)
    return PortfolioPolicy(**fields)


def test_accepts_risk_md_initial_policy():
    policy = make_policy()
    assert policy.bucket_targets[Bucket.CORE] == Decimal("0.70")


def test_rejects_bucket_targets_not_summing_to_one():
    with pytest.raises(ValueError):
        make_policy(
            bucket_targets={
                Bucket.CORE: Decimal("0.5"),
                Bucket.GROWTH: Decimal("0.2"),
                Bucket.SPECULATIVE: Decimal("0.1"),
            }
        )


def test_rejects_missing_bucket_in_targets():
    with pytest.raises(ValueError):
        make_policy(bucket_targets={Bucket.CORE: Decimal("1")})


def test_rejects_operating_max_above_absolute_max():
    with pytest.raises(ValueError):
        make_policy(
            speculative_operating_max=Decimal("0.20"),
            speculative_absolute_max=Decimal("0.15"),
        )


def test_rejects_single_asset_max_above_operating_max():
    with pytest.raises(ValueError):
        make_policy(single_speculative_asset_max=Decimal("0.20"))


def test_rejects_nonpositive_max_open_positions():
    with pytest.raises(ValueError):
        make_policy(max_open_positions=0)


def test_state_rejects_nonpositive_equity():
    with pytest.raises(ValueError):
        PortfolioState(
            equity=Decimal("0"), bucket_exposure={}, asset_exposure={}, open_positions=0
        )


def test_state_rejects_negative_exposure():
    with pytest.raises(ValueError):
        PortfolioState(
            equity=Decimal("1000"),
            bucket_exposure={Bucket.CORE: Decimal("-1")},
            asset_exposure={},
            open_positions=0,
        )


def test_approved_proposal_requires_positive_notional():
    with pytest.raises(ValueError):
        AllocationProposal(
            instrument=INSTRUMENT,
            bucket=Bucket.CORE,
            side=Side.BUY,
            version=1,
            as_of=AS_OF,
            proposed_notional=Decimal("0"),
            approved=True,
            reasons=(),
        )


def test_rejected_proposal_requires_zero_notional():
    with pytest.raises(ValueError):
        AllocationProposal(
            instrument=INSTRUMENT,
            bucket=Bucket.CORE,
            side=Side.BUY,
            version=1,
            as_of=AS_OF,
            proposed_notional=Decimal("100"),
            approved=False,
            reasons=("x",),
        )
