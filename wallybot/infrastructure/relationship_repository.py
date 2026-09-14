"""RelationshipRepository: persistence for the Entity Correlation Graph.

Insert-only, like `WalletRepository.save_cluster` -- a `Relationship` is one claim, not a
mutable, evolving identity like `Entity`/`Wallet`. Re-saving the same id is a caller error.
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.relationship import (
    NodeReference,
    NodeReferenceType,
    Relationship,
    RelationshipType,
)
from wallybot.infrastructure.models import RelationshipRow


class RelationshipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, relationship: Relationship) -> None:
        existing = await self.session.get(RelationshipRow, relationship.id)
        if existing is not None:
            raise ValueError(
                f"relationship {relationship.id} already exists; relationships are insert-only"
            )
        self.session.add(
            RelationshipRow(
                id=relationship.id,
                source_type=relationship.source.node_type,
                source_id=relationship.source.node_id,
                relationship_type=relationship.relationship_type,
                target_type=relationship.target.node_type,
                target_id=relationship.target.node_id,
                attribution_source=relationship.attribution.source,
                attribution_source_entity_id=relationship.attribution.source_entity_id,
                attribution_confidence=relationship.attribution.confidence,
                attribution_evidence=relationship.attribution.evidence,
                attribution_verification_status=relationship.attribution.verification_status,
                attribution_observed_at=relationship.attribution.observed_at,
                created_at=relationship.created_at,
            )
        )

    async def get(self, relationship_id: str) -> Relationship | None:
        row = await self.session.get(RelationshipRow, relationship_id)
        if row is None:
            return None
        return self._to_domain(row)

    async def find_by_node(
        self, node_type: NodeReferenceType, node_id: str
    ) -> tuple[Relationship, ...]:
        """Every relationship touching a node, on either side -- the basic traversal a
        correlation graph needs regardless of whether the node is the source or the target."""
        rows = (
            (
                await self.session.execute(
                    select(RelationshipRow).where(
                        (
                            (RelationshipRow.source_type == node_type)
                            & (RelationshipRow.source_id == node_id)
                        )
                        | (
                            (RelationshipRow.target_type == node_type)
                            & (RelationshipRow.target_id == node_id)
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    async def list_recent(self, limit: int = 100) -> tuple[Relationship, ...]:
        """Newest-first across the whole graph -- a UI feed, as opposed to `find_by_node`'s
        node-scoped traversal."""
        rows = (
            (
                await self.session.execute(
                    select(RelationshipRow).order_by(desc(RelationshipRow.created_at)).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: RelationshipRow) -> Relationship:
        return Relationship(
            id=row.id,
            source=NodeReference(NodeReferenceType(row.source_type), row.source_id),
            relationship_type=RelationshipType(row.relationship_type),
            target=NodeReference(NodeReferenceType(row.target_type), row.target_id),
            attribution=Attribution(
                source=row.attribution_source,
                source_entity_id=row.attribution_source_entity_id,
                confidence=row.attribution_confidence,
                evidence=row.attribution_evidence,
                verification_status=VerificationStatus(row.attribution_verification_status),
                observed_at=row.attribution_observed_at,
            ),
            created_at=row.created_at,
        )
