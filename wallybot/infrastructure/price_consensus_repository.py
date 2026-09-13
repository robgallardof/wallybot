"""PriceConsensusRepository: append-only persistence for price consensus results.

`save` always inserts a new row -- same insert-only discipline as every other snapshot table in
this schema.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.price_consensus import PriceConsensusResult, PriceConsensusStatus
from wallybot.infrastructure.models import PriceConsensusResultRow


class PriceConsensusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, result: PriceConsensusResult) -> None:
        self.session.add(
            PriceConsensusResultRow(
                instrument_id=result.instrument_id,
                status=result.status,
                consensus_price=result.consensus_price,
                included_sources=list(result.included_sources),
                excluded_sources=list(result.excluded_sources),
                reasons=list(result.reasons),
                computed_at=result.computed_at,
            )
        )

    async def latest(self, instrument_id: str) -> PriceConsensusResult | None:
        row = (
            await self.session.execute(
                select(PriceConsensusResultRow)
                .where(PriceConsensusResultRow.instrument_id == instrument_id)
                .order_by(PriceConsensusResultRow.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def history(self, instrument_id: str) -> tuple[PriceConsensusResult, ...]:
        rows = (
            (
                await self.session.execute(
                    select(PriceConsensusResultRow)
                    .where(PriceConsensusResultRow.instrument_id == instrument_id)
                    .order_by(PriceConsensusResultRow.computed_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: PriceConsensusResultRow) -> PriceConsensusResult:
        return PriceConsensusResult(
            instrument_id=row.instrument_id,
            status=PriceConsensusStatus(row.status),
            consensus_price=row.consensus_price,
            included_sources=tuple(row.included_sources),
            excluded_sources=tuple(row.excluded_sources),
            reasons=tuple(row.reasons),
            computed_at=row.computed_at,
        )
