"""EntityRepository: persistence for the Entity Registry (ARCHITECTURE.md's "Multi-source
intelligence and Smart Money").

`save()` upserts an entity's mutable summary fields and appends any attribution not already
persisted -- attributions are append-only evidence, per "never assume an external attribution is
absolute truth," and `(entity_id, source, source_entity_id, observed_at)` is the dedup key that
lets a provider re-report the same claim without duplicating it.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.entity import Attribution, Entity, EntityType, VerificationStatus
from wallybot.infrastructure.models import EntityAttributionRow, EntityRow


class EntityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, entity: Entity) -> None:
        row = await self.session.get(EntityRow, entity.id)
        if row is None:
            row = EntityRow(id=entity.id)
            self.session.add(row)
        row.name = entity.name
        row.entity_type = entity.entity_type
        row.aliases = list(entity.aliases)
        row.description = entity.description
        row.enabled = entity.enabled
        row.confidence = entity.confidence
        row.trust_score = entity.trust_score
        row.risk_score = entity.risk_score
        row.influence_weight = entity.influence_weight
        row.tags = list(entity.tags)
        row.created_at = entity.created_at
        row.updated_at = entity.updated_at
        await self.session.flush()

        for attribution in entity.attributions:
            already_seen = await self._attribution_exists(entity.id, attribution)
            if already_seen:
                continue
            self.session.add(
                EntityAttributionRow(
                    entity_id=entity.id,
                    source=attribution.source,
                    source_entity_id=attribution.source_entity_id,
                    confidence=attribution.confidence,
                    evidence=attribution.evidence,
                    verification_status=attribution.verification_status,
                    observed_at=attribution.observed_at,
                )
            )

    async def _attribution_exists(self, entity_id: str, attribution: Attribution) -> bool:
        result = await self.session.execute(
            select(EntityAttributionRow.id).where(
                EntityAttributionRow.entity_id == entity_id,
                EntityAttributionRow.source == attribution.source,
                EntityAttributionRow.source_entity_id == attribution.source_entity_id,
                EntityAttributionRow.observed_at == attribution.observed_at,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get(self, entity_id: str) -> Entity | None:
        row = await self.session.get(EntityRow, entity_id)
        if row is None:
            return None
        attribution_rows = (
            (
                await self.session.execute(
                    select(EntityAttributionRow).where(EntityAttributionRow.entity_id == entity_id)
                )
            )
            .scalars()
            .all()
        )
        return Entity(
            id=row.id,
            name=row.name,
            entity_type=EntityType(row.entity_type),
            aliases=tuple(row.aliases),
            description=row.description,
            enabled=row.enabled,
            confidence=row.confidence,
            trust_score=row.trust_score,
            risk_score=row.risk_score,
            influence_weight=row.influence_weight,
            tags=tuple(row.tags),
            attributions=tuple(
                Attribution(
                    source=a.source,
                    source_entity_id=a.source_entity_id,
                    confidence=a.confidence,
                    evidence=a.evidence,
                    verification_status=VerificationStatus(a.verification_status),
                    observed_at=a.observed_at,
                )
                for a in attribution_rows
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
