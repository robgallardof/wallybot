from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, Entity, EntityType, VerificationStatus

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "arkham",
        "source_entity_id": "arkham-123",
        "confidence": Decimal("0.8"),
        "evidence": "labeled by Arkham entity intelligence",
        "verification_status": VerificationStatus.UNVERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_entity(**overrides: Any) -> Entity:
    fields: dict[str, Any] = {
        "id": "entity-1",
        "name": "Example Fund",
        "entity_type": EntityType.FUND,
        "aliases": ("Example",),
        "description": "A hypothetical fund used only in tests.",
        "enabled": True,
        "confidence": Decimal("0.9"),
        "trust_score": Decimal("0.7"),
        "risk_score": Decimal("0.2"),
        "influence_weight": Decimal("0.5"),
        "tags": ("fund",),
        "attributions": (make_attribution(),),
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return Entity(**fields)


def test_a_well_formed_entity_is_accepted() -> None:
    entity = make_entity()
    assert entity.entity_type is EntityType.FUND
    assert len(entity.attributions) == 1


def test_an_entity_requires_at_least_one_attribution() -> None:
    with pytest.raises(ValueError, match="attribution"):
        make_entity(attributions=())


@pytest.mark.parametrize("field", ["confidence", "trust_score", "risk_score", "influence_weight"])
def test_entity_scores_must_stay_within_the_unit_interval(field: str) -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        make_entity(**{field: Decimal("1.5")})


def test_entity_requires_an_id_and_a_name() -> None:
    with pytest.raises(ValueError, match="id is required"):
        make_entity(id="")
    with pytest.raises(ValueError, match="name is required"):
        make_entity(name="")


def test_entity_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(ValueError, match="updated_at cannot be before created_at"):
        make_entity(created_at=NOW, updated_at=datetime(2025, 1, 1, tzinfo=UTC))


def test_entity_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="aware"):
        make_entity(created_at=datetime(2026, 1, 1))


def test_attribution_requires_source_and_evidence() -> None:
    with pytest.raises(ValueError, match="source is required"):
        make_attribution(source="")
    with pytest.raises(ValueError, match="evidence is required"):
        make_attribution(evidence="")


def test_attribution_confidence_must_stay_within_the_unit_interval() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        make_attribution(confidence=Decimal("-0.01"))


def test_attribution_source_entity_id_may_be_absent() -> None:
    attribution = make_attribution(source_entity_id=None)
    assert attribution.source_entity_id is None
