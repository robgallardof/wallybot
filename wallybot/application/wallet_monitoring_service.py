"""WalletMonitoringService: the ingestion loop for Phase 10 Slice 5's "on-chain event ingestion."

ARCHITECTURE.md's own preference is "event/webhook subscriptions... preferred over polling" --
this service is deliberately the polling fallback, not the final shape: nothing in this codebase
has a webhook receiver endpoint yet, and no real wallet-intelligence vendor is connected (Phase 10
Slice 4b is blocked on API credentials). Once a real provider exists, whether it exposes a webhook
subscription or must be polled is that adapter's own design question -- this service's job stops
at "fetch activity since some point in time, persist anything new," which is the same operation
whether the fetch is triggered by a poll timer or a webhook wake-up.

Mirrors `ReconciliationService`'s shape exactly: one wallet's failure is captured as its own
outcome rather than aborting the sync for the rest.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.wallet_activity import WalletActivityEvent, WalletIntelligenceProvider
from wallybot.infrastructure.wallet_activity_repository import WalletActivityRepository
from wallybot.infrastructure.wallet_repository import WalletRepository


@dataclass(frozen=True)
class WalletSyncOutcome:
    chain: str
    address: str
    new_events: tuple[WalletActivityEvent, ...]
    error: str | None


class WalletMonitoringService:
    def __init__(
        self, provider: WalletIntelligenceProvider, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        self.provider = provider
        self.sessions = sessions

    async def sync_wallet(
        self, chain: str, address: str, since: datetime
    ) -> tuple[WalletActivityEvent, ...]:
        events = await self.provider.fetch_wallet_activity(chain, address, since)
        new_events = []
        async with self.sessions.begin() as session:
            repo = WalletActivityRepository(session)
            for event in events:
                if await repo.save(chain, address, event):
                    new_events.append(event)
        return tuple(new_events)

    async def sync_all_enabled_wallets(self, since: datetime) -> tuple[WalletSyncOutcome, ...]:
        async with self.sessions() as session:
            wallets = await WalletRepository(session).list_enabled_wallets()

        outcomes = []
        for chain, address in wallets:
            try:
                new_events = await self.sync_wallet(chain, address, since)
                outcomes.append(WalletSyncOutcome(chain, address, new_events, None))
            except Exception as exc:  # noqa: BLE001 -- one wallet's failure must not abort the sync
                outcomes.append(WalletSyncOutcome(chain, address, (), str(exc)))
        return tuple(outcomes)
