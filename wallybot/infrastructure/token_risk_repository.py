"""TokenRiskScoreRepository: append-only persistence for token risk score history.

`save` always inserts a new row -- there is no update path at all, matching
`SmartMoneyScoreRepository`'s discipline: a token's risk profile can change over time, and history
should show that rather than overwrite it.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.token_risk import TokenRiskScore, TokenRiskStatus
from wallybot.infrastructure.models import TokenRiskScoreRow


class TokenRiskScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, score: TokenRiskScore) -> None:
        self.session.add(
            TokenRiskScoreRow(
                token_id=score.token_id,
                chain=score.chain,
                version=score.version,
                status=score.status,
                risk_score=score.risk_score,
                reasons=list(score.reasons),
                computed_at=score.computed_at,
            )
        )

    async def latest(self, chain: str, token_id: str) -> TokenRiskScore | None:
        row = (
            await self.session.execute(
                select(TokenRiskScoreRow)
                .where(TokenRiskScoreRow.chain == chain, TokenRiskScoreRow.token_id == token_id)
                .order_by(TokenRiskScoreRow.computed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return None if row is None else self._to_domain(row)

    async def list_latest(self) -> tuple[TokenRiskScore, ...]:
        """One row per (chain, token): its most recent score, newest-evaluated token first.
        Backs a UI/API listing -- per-token history stays available via `history`."""
        rows = (
            (
                await self.session.execute(
                    select(TokenRiskScoreRow)
                    .distinct(TokenRiskScoreRow.chain, TokenRiskScoreRow.token_id)
                    .order_by(
                        TokenRiskScoreRow.chain,
                        TokenRiskScoreRow.token_id,
                        TokenRiskScoreRow.computed_at.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(
            sorted(
                (self._to_domain(row) for row in rows),
                key=lambda score: score.computed_at,
                reverse=True,
            )
        )

    async def history(self, chain: str, token_id: str) -> tuple[TokenRiskScore, ...]:
        rows = (
            (
                await self.session.execute(
                    select(TokenRiskScoreRow)
                    .where(TokenRiskScoreRow.chain == chain, TokenRiskScoreRow.token_id == token_id)
                    .order_by(TokenRiskScoreRow.computed_at)
                )
            )
            .scalars()
            .all()
        )
        return tuple(self._to_domain(row) for row in rows)

    def _to_domain(self, row: TokenRiskScoreRow) -> TokenRiskScore:
        return TokenRiskScore(
            token_id=row.token_id,
            chain=row.chain,
            version=row.version,
            status=TokenRiskStatus(row.status),
            risk_score=row.risk_score,
            reasons=tuple(row.reasons),
            computed_at=row.computed_at,
        )
