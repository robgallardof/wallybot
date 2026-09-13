from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.relationship import (
    NodeReference,
    NodeReferenceType,
    Relationship,
    RelationshipType,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_attribution(**overrides: Any) -> Attribution:
    fields: dict[str, Any] = {
        "source": "arkham",
        "source_entity_id": None,
        "confidence": Decimal("0.7"),
        "evidence": "on-chain transfer observed",
        "verification_status": VerificationStatus.UNVERIFIED,
        "observed_at": NOW,
    }
    fields.update(overrides)
    return Attribution(**fields)


def make_relationship(**overrides: Any) -> Relationship:
    fields: dict[str, Any] = {
        "id": "rel-1",
        "source": NodeReference(NodeReferenceType.WALLET, "ethereum:0xabc"),
        "relationship_type": RelationshipType.TRANSFERRED_TO,
        "target": NodeReference(NodeReferenceType.WALLET, "ethereum:0xdef"),
        "attribution": make_attribution(),
        "created_at": NOW,
    }
    fields.update(overrides)
    return Relationship(**fields)


def test_a_well_formed_relationship_is_accepted() -> None:
    relationship = make_relationship()
    assert relationship.relationship_type is RelationshipType.TRANSFERRED_TO


def test_relationship_requires_an_id() -> None:
    with pytest.raises(ValueError, match="id is required"):
        make_relationship(id="")


def test_relationship_rejects_a_self_referencing_edge() -> None:
    same = NodeReference(NodeReferenceType.WALLET, "ethereum:0xabc")
    with pytest.raises(ValueError, match="cannot link a node to itself"):
        make_relationship(source=same, target=same)


def test_relationship_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="aware"):
        make_relationship(created_at=datetime(2026, 1, 1))


def test_node_reference_requires_a_node_id() -> None:
    with pytest.raises(ValueError, match="node_id is required"):
        NodeReference(NodeReferenceType.TOKEN, "")


def test_an_entity_and_wallet_can_be_related_across_different_node_types() -> None:
    relationship = make_relationship(
        source=NodeReference(NodeReferenceType.ENTITY, "entity-1"),
        relationship_type=RelationshipType.CONTROLS,
        target=NodeReference(NodeReferenceType.WALLET, "ethereum:0xabc"),
    )
    assert relationship.source.node_type is NodeReferenceType.ENTITY
    assert relationship.target.node_type is NodeReferenceType.WALLET
