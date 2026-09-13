"""ReconciliationService: periodically sweeps every non-terminal order and asks the gateway to
resolve it, per DATA.md: "Run at startup, before LIVE activation, periodically, after ambiguous
requests, and after reconnects ... Reconciliation is account-scoped ... and restartable."

This composes `ExecutionService.reconcile_order` (Slice 5) across every open order rather than
one at a time -- it adds no new resolution logic of its own. One order's failure is recorded and
does not abort the sweep for the others (DATA.md: "Do not treat a partial/failed fetch as an
empty account" -- the analogous principle here is that one bad order must not look like a clean
sweep of the rest).

Explicitly out of scope: balance/position comparison against the venue (`ExchangeGateway` has no
balance-fetching method yet -- nothing before this needs one), persisted discrepancy evidence
beyond the returned outcomes, pagination over exchange history (`list_fills`/`lookup_order` are
both already scoped to one order). A real venue's reconciliation would need all of these; this
sweep only reconciles what Phase 4's own orders already track.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.execution_service import ExecutionService
from wallybot.domain.order import OrderStatus
from wallybot.infrastructure.unit_of_work import unit_of_work


@dataclass(frozen=True)
class ReconciliationOutcome:
    client_order_id: str
    resolved_status: OrderStatus | None
    error: str | None


class ReconciliationService:
    def __init__(
        self, execution: ExecutionService, sessions: async_sessionmaker[AsyncSession]
    ) -> None:
        self.execution = execution
        self.sessions = sessions

    async def sweep(self, environment: str) -> tuple[ReconciliationOutcome, ...]:
        async with unit_of_work(self.sessions) as uow:
            open_orders = await uow.list_open_order_intents(environment)

        outcomes = []
        for client_order_id, venue, account_id, order_environment in open_orders:
            try:
                status = await self.execution.reconcile_order(
                    client_order_id, venue, account_id, order_environment
                )
                outcomes.append(ReconciliationOutcome(client_order_id, status, None))
            except Exception as exc:  # noqa: BLE001 -- one order's failure must not abort the sweep
                outcomes.append(ReconciliationOutcome(client_order_id, None, str(exc)))
        return tuple(outcomes)
