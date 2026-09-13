from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.market_metadata import TokenMarketMetadata

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_metadata(**overrides: Any) -> TokenMarketMetadata:
    fields: dict[str, Any] = {
        "token_id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "market_cap_usd": Decimal("1550502144718"),
        "fully_diluted_valuation_usd": Decimal("1550506236454"),
        "volume_24h_usd": Decimal("15292184429"),
        "circulating_supply": Decimal("20083556"),
        "total_supply": Decimal("20083609"),
        "max_supply": Decimal("21000000"),
        "source": "coingecko",
        "source_updated_at": NOW,
        "fetched_at": NOW,
    }
    fields.update(overrides)
    return TokenMarketMetadata(**fields)


def test_a_well_formed_metadata_record_is_accepted() -> None:
    metadata = make_metadata()
    assert metadata.symbol == "btc"


def test_max_supply_may_be_absent_for_a_token_with_no_hard_cap() -> None:
    metadata = make_metadata(max_supply=None)
    assert metadata.max_supply is None


@pytest.mark.parametrize("field", ["token_id", "symbol", "name", "source"])
def test_required_identity_fields_cannot_be_empty(field: str) -> None:
    with pytest.raises(ValueError, match="required"):
        make_metadata(**{field: ""})


@pytest.mark.parametrize(
    "field",
    [
        "market_cap_usd",
        "fully_diluted_valuation_usd",
        "volume_24h_usd",
        "circulating_supply",
        "total_supply",
        "max_supply",
    ],
)
def test_optional_numeric_fields_cannot_be_negative_when_present(field: str) -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        make_metadata(**{field: Decimal("-1")})


def test_source_updated_at_must_be_aware() -> None:
    with pytest.raises(ValueError, match="aware"):
        make_metadata(source_updated_at=datetime(2026, 1, 1))


def test_fetched_at_must_be_aware() -> None:
    with pytest.raises(ValueError, match="aware"):
        make_metadata(fetched_at=datetime(2026, 1, 1))
