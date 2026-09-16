from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.experiment import ExperimentRecord

NOW = datetime(2026, 1, 10, tzinfo=UTC)
WINDOW_START = datetime(2026, 1, 1, tzinfo=UTC)
WINDOW_END = datetime(2026, 1, 8, tzinfo=UTC)


def make_record(**overrides) -> ExperimentRecord:
    fields: dict[str, object] = {
        "experiment_id": "exp-1",
        "strategy_id": "trend_following",
        "strategy_version": 1,
        "feature_engine_version": 1,
        "backtest_engine_version": 1,
        "instrument_venue": "kraken",
        "instrument_market_type": "SPOT",
        "instrument_base": "BTC",
        "instrument_quote": "USD",
        "price_increment": Decimal("0.01"),
        "quantity_increment": Decimal("0.0001"),
        "min_quantity": Decimal("0.0001"),
        "timeframe": "1h",
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "feature_window": 20,
        "risk_off_threshold": Decimal("0.1"),
        "fee_rate": Decimal("0.001"),
        "slippage_pct": Decimal("0.0005"),
        "starting_equity": Decimal("10000"),
        "allocation_pct": Decimal("0.1"),
        "seed": 42,
        "trade_count": 3,
        "final_equity": Decimal("10500"),
        "total_return_pct": Decimal("0.05"),
        "max_drawdown_pct": Decimal("0.02"),
        "win_rate": Decimal("0.667"),
        "created_at": NOW,
    }
    fields.update(overrides)
    return ExperimentRecord(**fields)  # type: ignore[arg-type]


def test_a_valid_record_constructs() -> None:
    record = make_record()
    assert record.experiment_id == "exp-1"


def test_a_record_with_no_bootstrap_seed_constructs() -> None:
    record = make_record(seed=None)
    assert record.seed is None


@pytest.mark.parametrize(
    "field",
    [
        "experiment_id",
        "strategy_id",
        "instrument_venue",
        "instrument_market_type",
        "instrument_base",
        "timeframe",
    ],
)
def test_required_identifier_fields_reject_empty_string(field: str) -> None:
    with pytest.raises(ValueError, match="required"):
        make_record(**{field: ""})


@pytest.mark.parametrize("field", ["price_increment", "quantity_increment", "min_quantity"])
def test_nonpositive_precision_fields_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="positive"):
        make_record(**{field: Decimal("0")})


def test_window_end_before_start_rejected() -> None:
    with pytest.raises(ValueError, match="window_end"):
        make_record(window_start=WINDOW_END, window_end=WINDOW_START)


def test_nonpositive_strategy_version_rejected() -> None:
    with pytest.raises(ValueError, match="strategy_version"):
        make_record(strategy_version=0)


def test_fee_rate_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="fee_rate"):
        make_record(fee_rate=Decimal("1.5"))


def test_nonpositive_starting_equity_rejected() -> None:
    with pytest.raises(ValueError, match="starting_equity"):
        make_record(starting_equity=Decimal(0))


def test_allocation_pct_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="allocation_pct"):
        make_record(allocation_pct=Decimal(0))


def test_negative_trade_count_rejected() -> None:
    with pytest.raises(ValueError, match="trade_count"):
        make_record(trade_count=-1)


def test_win_rate_out_of_range_rejected() -> None:
    with pytest.raises(ValueError, match="win_rate"):
        make_record(win_rate=Decimal("1.5"))


def test_naive_created_at_rejected() -> None:
    with pytest.raises(ValueError, match="created_at"):
        make_record(created_at=datetime(2026, 1, 10))
