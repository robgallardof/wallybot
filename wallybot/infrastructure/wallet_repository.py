"""WalletRepository: persistence for the Wallet Registry and wallet clusters
(ARCHITECTURE.md's "Multi-source intelligence and Smart Money").

Same upsert-plus-append-only-attributions shape as `EntityRepository`. `WalletCluster` rows are
insert-only (a cluster is a point-in-time observation of convergence, not a mutable entity) --
saving a cluster whose id already exists is a caller error, not silently accepted.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wallybot.domain.entity import Attribution, VerificationStatus
from wallybot.domain.wallet import MonitoringMode, Wallet, WalletCluster
from wallybot.infrastructure.models import (
    WalletAttributionRow,
    WalletClusterMemberRow,
    WalletClusterRow,
    WalletRow,
)


class WalletRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, wallet: Wallet) -> None:
        row = await self.session.get(WalletRow, (wallet.chain, wallet.address))
        if row is None:
            row = WalletRow(chain=wallet.chain, address=wallet.address)
            self.session.add(row)
        row.entity_id = wallet.entity_id
        row.alias = wallet.alias
        row.labels = list(wallet.labels)
        row.tags = list(wallet.tags)
        row.confidence = wallet.confidence
        row.trust_score = wallet.trust_score
        row.risk_score = wallet.risk_score
        row.enabled = wallet.enabled
        row.monitoring_mode = wallet.monitoring_mode
        row.influence_weight = wallet.influence_weight
        row.max_signal_weight = wallet.max_signal_weight
        row.max_allocation = wallet.max_allocation
        row.min_transaction_value = wallet.min_transaction_value
        row.created_at = wallet.created_at
        row.updated_at = wallet.updated_at
        await self.session.flush()

        for attribution in wallet.attributions:
            already_seen = await self._attribution_exists(wallet.chain, wallet.address, attribution)
            if already_seen:
                continue
            self.session.add(
                WalletAttributionRow(
                    chain=wallet.chain,
                    address=wallet.address,
                    source=attribution.source,
                    source_entity_id=attribution.source_entity_id,
                    confidence=attribution.confidence,
                    evidence=attribution.evidence,
                    verification_status=attribution.verification_status,
                    observed_at=attribution.observed_at,
                )
            )

    async def _attribution_exists(self, chain: str, address: str, attribution: Attribution) -> bool:
        result = await self.session.execute(
            select(WalletAttributionRow.id).where(
                WalletAttributionRow.chain == chain,
                WalletAttributionRow.address == address,
                WalletAttributionRow.source == attribution.source,
                WalletAttributionRow.source_entity_id == attribution.source_entity_id,
                WalletAttributionRow.observed_at == attribution.observed_at,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get(self, chain: str, address: str) -> Wallet | None:
        row = await self.session.get(WalletRow, (chain, address))
        if row is None:
            return None
        attribution_rows = (
            (
                await self.session.execute(
                    select(WalletAttributionRow).where(
                        WalletAttributionRow.chain == chain, WalletAttributionRow.address == address
                    )
                )
            )
            .scalars()
            .all()
        )
        return Wallet(
            address=row.address,
            chain=row.chain,
            entity_id=row.entity_id,
            alias=row.alias,
            labels=tuple(row.labels),
            tags=tuple(row.tags),
            confidence=row.confidence,
            trust_score=row.trust_score,
            risk_score=row.risk_score,
            enabled=row.enabled,
            monitoring_mode=MonitoringMode(row.monitoring_mode),
            influence_weight=row.influence_weight,
            max_signal_weight=row.max_signal_weight,
            max_allocation=row.max_allocation,
            min_transaction_value=row.min_transaction_value,
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

    async def list_enabled_wallets(self) -> tuple[tuple[str, str], ...]:
        """`(chain, address)` for every enabled wallet -- what a monitoring sync iterates over.
        Monitoring mode governs how collected data is *used* downstream, not whether it is
        collected at all ("OBSERVE: collect data only" still means data gets collected)."""
        rows = (
            await self.session.execute(
                select(WalletRow.chain, WalletRow.address).where(WalletRow.enabled)
            )
        ).all()
        return tuple((row.chain, row.address) for row in rows)

    async def save_cluster(self, cluster: WalletCluster) -> None:
        existing = await self.session.get(WalletClusterRow, cluster.id)
        if existing is not None:
            raise ValueError(
                f"wallet cluster {cluster.id} already exists; clusters are insert-only"
            )
        self.session.add(
            WalletClusterRow(
                id=cluster.id,
                entity_id=cluster.entity_id,
                confidence=cluster.confidence,
                evidence=cluster.evidence,
                created_at=cluster.created_at,
            )
        )
        await self.session.flush()
        for wallet_id in cluster.wallet_ids:
            chain, address = wallet_id.split(":", 1)
            self.session.add(
                WalletClusterMemberRow(cluster_id=cluster.id, chain=chain, address=address)
            )

    async def get_cluster(self, cluster_id: str) -> WalletCluster | None:
        row = await self.session.get(WalletClusterRow, cluster_id)
        if row is None:
            return None
        member_rows = (
            (
                await self.session.execute(
                    select(WalletClusterMemberRow).where(
                        WalletClusterMemberRow.cluster_id == cluster_id
                    )
                )
            )
            .scalars()
            .all()
        )
        return WalletCluster(
            id=row.id,
            entity_id=row.entity_id,
            wallet_ids=tuple(f"{m.chain}:{m.address}" for m in member_rows),
            confidence=row.confidence,
            evidence=row.evidence,
            created_at=row.created_at,
        )
