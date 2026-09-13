"""WalletActivityRepository: persistence for ingested on-chain wallet activity.

`save` is idempotent: an event already seen (matched by the same dedup key the unique constraint
enforces) is silently skipped rather than raising, since a monitoring sync's `since` windows are
expected to overlap -- re-observing the same transaction is the normal case, not an error.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent
from wallybot.infrastructure.models import WalletActivityEventRow


class WalletActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, chain: str, address: str, event: WalletActivityEvent) -> bool:
        """Returns True if the event was newly persisted, False if it was already known."""
        if await self._exists(chain, address, event):
            return False
        self.session.add(
            WalletActivityEventRow(
                chain=chain,
                address=address,
                transaction_hash=event.transaction_hash,
                token=event.token,
                action=event.action,
                amount=event.amount,
                value_usd=event.value_usd,
                price=event.price,
                liquidity_usd=event.liquidity_usd,
                occurred_at=event.occurred_at,
                attribution_source=event.attribution.source,
                attribution_source_entity_id=event.attribution.source_entity_id,
                attribution_confidence=event.attribution.confidence,
                attribution_evidence=event.attribution.evidence,
                attribution_verification_status=event.attribution.verification_status,
                attribution_observed_at=event.attribution.observed_at,
            )
        )
        return True

    async def _exists(self, chain: str, address: str, event: WalletActivityEvent) -> bool:
        result = await self.session.execute(
            select(WalletActivityEventRow.id).where(
                WalletActivityEventRow.chain == chain,
                WalletActivityEventRow.address == address,
                WalletActivityEventRow.transaction_hash == event.transaction_hash,
                WalletActivityEventRow.token == event.token,
                WalletActivityEventRow.action == event.action,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_for_wallet(self, chain: str, address: str) -> tuple[WalletActivityEvent, ...]:
        rows = (
            (
                await self.session.execute(
                    select(WalletActivityEventRow).where(
                        WalletActivityEventRow.chain == chain,
                        WalletActivityEventRow.address == address,
                    )
                )
            )
            .scalars()
            .all()
        )
        return tuple(
            WalletActivityEvent(
                wallet_id=f"{chain}:{address}",
                chain=chain,
                transaction_hash=row.transaction_hash,
                token=row.token,
                action=OnChainActionType(row.action),
                amount=row.amount,
                value_usd=row.value_usd,
                price=row.price,
                liquidity_usd=row.liquidity_usd,
                occurred_at=row.occurred_at,
                attribution=Attribution(
                    source=row.attribution_source,
                    source_entity_id=row.attribution_source_entity_id,
                    confidence=row.attribution_confidence,
                    evidence=row.attribution_evidence,
                    verification_status=VerificationStatus(row.attribution_verification_status),
                    observed_at=row.attribution_observed_at,
                ),
            )
            for row in rows
        )
