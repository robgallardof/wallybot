"""ExecutionService: durably claims an already-approved `OrderIntent`, submits it through an
`ExchangeGateway`, and persists whatever was actually observed -- never more, never less.

Implements ADR-008 exactly: "persist stable client IDs ... before submission. Claim intent,
record SUBMITTING, submit, then persist observed status. Ambiguity enters UNKNOWN, retains
reservations and reconciles before retry." Concretely:

- `submit()` never calls the gateway a second time for an intent already past VALIDATED --
  resuming after a crash (whether before or after the SUBMITTING commit) is always safe, because
  the only two states a resumed call can find are VALIDATED (nothing happened yet -- proceed
  exactly as new) or something later (already claimed or resolved -- return it, untouched).
- A submission answered UNKNOWN is left at UNKNOWN. `submit()` does not retry it. Only
  `reconcile()` may move an order out of UNKNOWN, and only by asking the gateway what it actually
  knows -- never by blind resubmission.
- Fills are looked up and persisted idempotently (`UnitOfWork.fill_exists` first) so calling
  `reconcile()` or observing an already-filled order repeatedly never double-posts a fill or its
  ledger transaction.

Does not evaluate risk (that already happened before an intent reaches VALIDATED) and does not
orchestrate cancellation -- both are their own future slices.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.ledger_postings import build_fill_ledger_transaction
from wallybot.domain.clock import Clock
from wallybot.domain.execution import (
    ExchangeGateway,
    OrderLookup,
    SubmissionOutcome,
    VenueOrderStatus,
)
from wallybot.domain.order import (
    TERMINAL_STATUSES,
    InvalidOrderTransition,
    OrderIntent,
    OrderStatus,
    can_transition,
)
from wallybot.infrastructure.unit_of_work import unit_of_work

_VENUE_TO_ORDER_STATUS: dict[VenueOrderStatus, OrderStatus] = {
    VenueOrderStatus.ACKNOWLEDGED: OrderStatus.ACKNOWLEDGED,
    VenueOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
    VenueOrderStatus.FILLED: OrderStatus.FILLED,
    VenueOrderStatus.CANCELLED: OrderStatus.CANCELLED,
    VenueOrderStatus.REJECTED: OrderStatus.REJECTED,
}


class ExecutionService:
    def __init__(
        self,
        gateway: ExchangeGateway,
        sessions: async_sessionmaker[AsyncSession],
        clock: Clock,
    ) -> None:
        self.gateway = gateway
        self.sessions = sessions
        self.clock = clock

    async def submit(self, intent: OrderIntent) -> OrderStatus:
        if intent.status != OrderStatus.VALIDATED:
            raise ValueError(f"submit requires a VALIDATED intent, got {intent.status}")

        existing = await self._current_status(intent.client_order_id)
        if existing is None:
            async with unit_of_work(self.sessions) as uow:
                await uow.save_order_intent(intent)
            existing = OrderStatus.VALIDATED

        if existing is not OrderStatus.VALIDATED:
            # Either already claimed by an earlier attempt (crash-recovery replay landed here
            # while SUBMITTING) or already resolved -- in neither case is it safe or useful to
            # call the gateway again. SUBMITTING in particular can only move forward via
            # reconcile(), never a second submit_order call.
            return existing

        now = self.clock.now()
        async with unit_of_work(self.sessions) as uow:
            await uow.update_order_status(
                intent.client_order_id, OrderStatus.VALIDATED, OrderStatus.SUBMITTING, now
            )
        # The durable claim is committed. Only now do we call the exchange -- never hold a
        # database transaction open across the network call.
        submitting = intent.transition_to(OrderStatus.SUBMITTING)
        result = await self.gateway.submit_order(submitting)
        now = self.clock.now()

        if result.outcome is SubmissionOutcome.REJECTED:
            async with unit_of_work(self.sessions) as uow:
                await uow.update_order_status(
                    intent.client_order_id, OrderStatus.SUBMITTING, OrderStatus.REJECTED, now
                )
            return OrderStatus.REJECTED

        if result.outcome is SubmissionOutcome.UNKNOWN:
            async with unit_of_work(self.sessions) as uow:
                await uow.update_order_status(
                    intent.client_order_id, OrderStatus.SUBMITTING, OrderStatus.UNKNOWN, now
                )
            return OrderStatus.UNKNOWN

        async with unit_of_work(self.sessions) as uow:
            await uow.update_order_status(
                intent.client_order_id, OrderStatus.SUBMITTING, OrderStatus.SUBMITTED, now
            )
            await uow.update_order_status(
                intent.client_order_id, OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED, now
            )
        return await self._observe(
            intent.client_order_id,
            intent.instrument.venue,
            intent.account_id,
            intent.environment,
            OrderStatus.ACKNOWLEDGED,
        )

    async def reconcile(self, intent: OrderIntent) -> OrderStatus:
        """Reconcile one order this process still holds a full `OrderIntent` for (the common
        case: right after `submit()` returned UNKNOWN). For reconciling orders known only from
        persisted state -- a scheduled sweep, say -- see `reconcile_order`."""
        return await self.reconcile_order(
            intent.client_order_id, intent.instrument.venue, intent.account_id, intent.environment
        )

    async def reconcile_order(
        self, client_order_id: str, venue: str, account_id: str, environment: str
    ) -> OrderStatus:
        current_status = await self._current_status(client_order_id)
        if current_status is None:
            raise ValueError(f"no such order_intent: {client_order_id}")
        if current_status in TERMINAL_STATUSES:
            return current_status

        if current_status is OrderStatus.SUBMITTING:
            # Resuming and finding SUBMITTING *is* the ambiguity ADR-008 describes: we cannot
            # know whether the network call ever went out. Move to UNKNOWN first -- exactly the
            # diagram's own "SUBMITTING --> UNKNOWN: Timeout or crash" edge -- then resolve from
            # whatever the gateway actually reports.
            now = self.clock.now()
            async with unit_of_work(self.sessions) as uow:
                await uow.update_order_status(
                    client_order_id, current_status, OrderStatus.UNKNOWN, now
                )
            current_status = OrderStatus.UNKNOWN

        lookup = await self.gateway.lookup_order(client_order_id)
        if lookup.status is VenueOrderStatus.NOT_FOUND:
            if current_status is not OrderStatus.UNKNOWN:
                raise ValueError(
                    f"gateway has no record of {client_order_id}, but its recorded "
                    f"status is {current_status}, not UNKNOWN"
                )
            now = self.clock.now()
            async with unit_of_work(self.sessions) as uow:
                await uow.update_order_status(
                    client_order_id, current_status, OrderStatus.VALIDATED, now
                )
            return OrderStatus.VALIDATED

        return await self._observe(
            client_order_id, venue, account_id, environment, current_status, lookup
        )

    async def _current_status(self, client_order_id: str) -> OrderStatus | None:
        async with unit_of_work(self.sessions) as uow:
            return await uow.get_order_status(client_order_id)

    async def _observe(
        self,
        client_order_id: str,
        venue: str,
        account_id: str,
        environment: str,
        current_status: OrderStatus,
        lookup: OrderLookup | None = None,
    ) -> OrderStatus:
        lookup = lookup or await self.gateway.lookup_order(client_order_id)
        if lookup.status is VenueOrderStatus.NOT_FOUND:
            raise ValueError(f"gateway lost track of {client_order_id} after acknowledging it")
        target = _VENUE_TO_ORDER_STATUS[lookup.status]
        now = self.clock.now()
        async with unit_of_work(self.sessions) as uow:
            if target is not current_status:
                if not can_transition(current_status, target):
                    raise InvalidOrderTransition(
                        f"gateway observed {target} from {current_status}, which is not a "
                        "valid transition"
                    )
                await uow.update_order_status(client_order_id, current_status, target, now)
            for fill in await self.gateway.list_fills(client_order_id):
                already_seen = await uow.fill_exists(venue, account_id, environment, fill.fill_id)
                if already_seen:
                    continue
                uow.save_fill(fill, account_id=account_id, environment=environment)
                await uow.save_ledger_transaction(
                    build_fill_ledger_transaction(fill, account_id=account_id)
                )
        return target
