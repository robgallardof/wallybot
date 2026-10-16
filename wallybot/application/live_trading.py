"""Approved, bounded spot execution against a reconciled real account.

No analyst holds this capability. Activation and approvals belong to the MFA-protected API.
External account changes block execution instead of silently resetting accounting or losses.
"""

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import select, text

from wallybot.application.decision_loop import BUCKET, PORTFOLIO_POLICY
from wallybot.application.equity_tracker import EquityAssessment
from wallybot.application.execution_service import ExecutionService
from wallybot.application.live_venues import (
    BinanceVenue,
    InvalidBookEvidence,
    KrakenVenue,
    LiveVenue,
)
from wallybot.application.position_monitoring import trustworthy_mark
from wallybot.application.proposal_execution import (
    ProposalExecutionResult,
    ProposalExecutionStatus,
    _revalidate,
    is_proposal_expired,
)
from wallybot.application.reconciliation_service import ReconciliationService
from wallybot.domain.control import Environment, Status
from wallybot.domain.equity import (
    EquitySnapshot,
    compute_daily_loss,
    compute_drawdown,
    compute_weekly_loss,
    next_high_water_mark,
)
from wallybot.domain.ledger import AccountPurpose, LedgerAccount, LedgerPosting, LedgerTransaction
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.order import TERMINAL_STATUSES, OrderIntent, OrderKind, OrderStatus, Side
from wallybot.domain.portfolio import Bucket, PortfolioState
from wallybot.domain.risk import RiskDecision
from wallybot.domain.trade_proposal import TradeDirection
from wallybot.exchanges.private_errors import ExchangePrivateError, TransientExchangeError
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.live_models import AnalystPortfolioRow, LiveControlRow
from wallybot.infrastructure.models import (
    AiAutonomyControlRow,
    ControlRow,
    OrderIntentRow,
    ProviderConnectionRow,
)
from wallybot.infrastructure.portfolio_repository import PortfolioRepository
from wallybot.infrastructure.shadow_decision_repository import ShadowDecisionRepository
from wallybot.infrastructure.unit_of_work import unit_of_work
from wallybot.security.auth import audit

# Consecutive transient venue failures (≈30 s apart) tolerated before the monitor blocks LIVE.
TRANSIENT_FAILURES_BEFORE_BLOCK = 3


class LiveBlocked(Exception):
    pass


def account_id(config: LiveControlRow) -> str:
    return "live:" + config.connection_id


def mandate_version(row):
    values = (row.target_core_pct, row.target_growth_pct, row.target_speculative_pct)
    digest = hashlib.sha256("|".join(str(value.normalize()) for value in values).encode()).digest()
    return int.from_bytes(digest[:4], "big")


class LiveTradingService:
    def __init__(
        self,
        engine,
        sessions,
        crypto,
        transport_factory,
        provider,
        clock,
        capable=lambda: False,
        binance_transport_factory=None,
        binance_provider=None,
    ):
        self.engine = engine
        self.sessions = sessions
        self.crypto = crypto
        # Kraken attributes keep their original names; Binance is a second, separate venue.
        self.transport_factory = transport_factory
        self.provider = provider
        self.binance_transport_factory = binance_transport_factory
        self.binance_provider = binance_provider
        self.clock = clock
        self.capable = capable
        self._transient_failures = 0

    def venue(self, connection_provider: str) -> LiveVenue:
        if connection_provider == "KRAKEN":
            return KrakenVenue(self.provider)
        if connection_provider == "BINANCE" and self.binance_provider is not None:
            return BinanceVenue(self.binance_provider)
        raise LiveBlocked("Select a verified spot trading connection")

    def _factory(self, connection_provider: str):
        if connection_provider == "BINANCE":
            return self.binance_transport_factory
        return self.transport_factory

    @asynccontextmanager
    async def serialized(self, wait_seconds: float = 0):
        # One configured real account. Try rather than queue stale approvals behind HTTP;
        # operator configuration may wait out the 30 s monitor's short reconciliation window.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + wait_seconds
        async with self.engine.connect() as connection:
            while True:
                locked = await connection.scalar(text("SELECT pg_try_advisory_lock(87321043)"))
                await connection.commit()
                if locked or loop.time() >= deadline:
                    break
                await asyncio.sleep(0.25)
            if not locked:
                raise LiveBlocked("Real account is being reconciled; retry after it completes")
            try:
                yield
                await connection.execute(text("SELECT pg_advisory_unlock(87321043)"))
                await connection.commit()
            except BaseException:
                await connection.invalidate()
                raise

    async def configuration(self, owner_id=None):
        async with self.sessions() as db:
            config = await db.get(LiveControlRow, 1)
        if config is not None and owner_id is not None and config.owner_id != owner_id:
            raise LiveBlocked("Real account belongs to another operator")
        return config

    async def account(self, config) -> tuple[LiveVenue, Any]:
        """The configured connection's venue and an authenticated transport for it."""
        async with self.sessions() as db:
            connection = await db.get(ProviderConnectionRow, config.connection_id)
        if (
            connection is None
            or connection.user_id != config.owner_id
            or connection.provider not in {"KRAKEN", "BINANCE"}
            or connection.mode != "TRADE_ONLY"
            or not connection.encrypted_key
            or not connection.encrypted_secret
        ):
            raise LiveBlocked("Select a verified spot trading connection")
        factory = self._factory(connection.provider)
        if factory is None:
            raise LiveBlocked("Select a verified spot trading connection")
        return self.venue(connection.provider), factory(
            self.crypto.decrypt(connection.encrypted_key),
            self.crypto.decrypt(connection.encrypted_secret),
        )

    async def load_intent(self, client_id):
        async with self.sessions() as db:
            row = await db.get(OrderIntentRow, client_id)
        if row is None:
            raise LiveBlocked("Unknown durable order identity")
        return OrderIntent(
            account_id=row.account_id,
            environment=row.environment,
            instrument=Instrument(row.venue, MarketType.SPOT, row.base, row.quote),
            side=Side(row.side),
            kind=OrderKind(row.kind),
            quantity=row.quantity,
            limit_price=row.limit_price,
            decision_id=row.decision_id,
            client_order_id=row.client_order_id,
            idempotency_key=row.idempotency_key,
            risk_assessment_id=row.risk_assessment_id,
            config_versions=row.config_versions,
            created_at=row.created_at,
            expires_at=row.expires_at,
            status=OrderStatus(row.status),
        )

    async def authorize(self, intent):
        async with self.sessions() as db:
            config = await db.get(LiveControlRow, 1)
            control = await db.get(ControlRow, 1)
            mandate = await db.get(AiAutonomyControlRow, 1)
        return bool(
            self.capable()
            and config
            and control
            and config.enabled
            and config.state == "READY"
            and control.environment == Environment.LIVE
            and control.status == Status.RUNNING
            and intent.account_id == account_id(config)
            and intent.config_versions.get("live") == config.version
            and mandate is not None
            and intent.config_versions.get("mandate") == mandate_version(mandate)
            and intent.expires_at > self.clock.now()
        )

    async def _sync(self, config, *, initialize=False):
        venue, transport = await self.account(config)
        await venue.verify_key(transport)
        gateway = venue.gateway(transport, self.load_intent, self.clock.now, self.authorize)
        execution = ExecutionService(gateway, self.sessions, self.clock)
        outcomes = await ReconciliationService(execution, self.sessions).sweep(
            "LIVE", account_id(config)
        )
        from wallybot.infrastructure.models import TradeProposalRow

        async with self.sessions.begin() as db:
            for outcome in outcomes:
                if outcome.error is not None or outcome.resolved_status is None:
                    continue
                proposal = await db.scalar(
                    select(TradeProposalRow).where(
                        TradeProposalRow.execution_order_id == outcome.client_order_id,
                        TradeProposalRow.owner_id == config.owner_id,
                        TradeProposalRow.execution_environment == "LIVE",
                    )
                )
                if (
                    proposal is not None
                    and proposal.execution_status != outcome.resolved_status.value
                ):
                    proposal.execution_status = outcome.resolved_status.value
                    audit(db, "LIVE_ORDER_RECONCILED", config.owner_id)
        if any(item.error or item.resolved_status not in TERMINAL_STATUSES for item in outcomes):
            raise LiveBlocked("An outstanding order needs reconciliation before another trade")
        if await venue.has_open_orders(transport):
            raise LiveBlocked("Open exchange orders must be resolved before activating or trading")
        balances = await venue.balances(transport)
        if any(total != available for total, available in balances.values()):
            raise LiveBlocked("Exchange funds are reserved; reconciliation is incomplete")
        if any(asset not in venue.assets and total for asset, (total, _) in balances.items()):
            raise LiveBlocked(venue.unsupported_assets_message)
        now = self.clock.now()
        async with self.sessions() as db:
            ledger = await PortfolioRepository(db).list_balances(account_id(config))
        expected = {b.currency: b.amount for b in ledger if b.amount}
        actual = {asset: total for asset, (total, _) in balances.items() if total}
        if not config.initialized:
            if not initialize or expected:
                raise LiveBlocked("Real opening balances require explicit activation")
            postings = []
            for asset, total in actual.items():
                purpose = AccountPurpose.CASH if asset == venue.cash else AccountPurpose.POSITION
                postings.extend(
                    (
                        LedgerPosting(LedgerAccount(account_id(config), asset, purpose), total),
                        LedgerPosting(
                            LedgerAccount("clearing", asset, AccountPurpose.CLEARING), -total
                        ),
                    )
                )
            if not postings:
                raise LiveBlocked("Real account has no funds")
            transaction = LedgerTransaction(
                str(uuid4()),
                account_id(config),
                "LIVE_OPENING_BALANCE",
                "live-opening:" + config.connection_id,
                tuple(postings),
                now,
            )
            async with unit_of_work(self.sessions) as uow:
                await uow.save_ledger_transaction(transaction)
                stored = await uow.session.get(LiveControlRow, 1)
                if stored is None:
                    raise LiveBlocked("Real account configuration disappeared")
                stored.initialized = True
            config.initialized = True
        elif any(
            abs(expected.get(asset, Decimal(0)) - actual.get(asset, Decimal(0)))
            > Decimal("0.00000001")
            for asset in set(expected) | set(actual)
        ):
            raise LiveBlocked(
                "Exchange balances differ from the ledger; review external account activity"
            )
        instruments = await venue.market.discover_instruments()
        exposures = {}
        for asset, total in actual.items():
            if asset == venue.cash:
                continue
            instrument = next(
                (
                    i
                    for i in instruments
                    if i.base == asset and i.quote == venue.cash and i.venue == venue.name
                ),
                None,
            )
            if instrument is None:
                raise LiveBlocked("A held asset has no supported USD valuation")
            quote = await venue.market.fetch_snapshot(instrument)
            # Judge freshness when the quote is used; providers stamp quotes on arrival.
            if not trustworthy_mark(quote, instrument, self.clock.now()):
                raise LiveBlocked("A held asset has no trustworthy current valuation")
            exposures[instrument.id] = total * quote.bid
        equity = actual.get(venue.cash, Decimal(0)) + sum(exposures.values(), Decimal(0))
        if equity <= 0:
            raise LiveBlocked("Real equity is not positive")
        async with self.sessions() as db:
            repository = EquitySnapshotRepository(db)
            previous = await repository.latest(account_id(config), "LIVE")
            history = await repository.recent(account_id(config), "LIVE", now - timedelta(days=8))
        high = next_high_water_mark(previous, equity)
        daily = compute_daily_loss(history, equity, now)
        weekly = compute_weekly_loss(history, equity, now)
        drawdown = compute_drawdown(equity, high)
        async with self.sessions.begin() as db:
            await EquitySnapshotRepository(db).save(
                EquitySnapshot(account_id(config), "LIVE", equity, high, now)
            )
            context = await db.get(AnalystPortfolioRow, config.owner_id)
            if context is None:
                context = AnalystPortfolioRow(owner_id=config.owner_id)
                db.add(context)
            context.cash_usd = actual.get(venue.cash, Decimal(0))
            context.holdings = {
                asset: str(total) for asset, total in actual.items() if asset != venue.cash
            }
            context.venue = venue.name
            context.as_of = now
        # Daily absolute budget uses the actual UTC-day baseline, not current-equity * ratio.
        daily_usd = equity * daily / (1 - daily) if daily < 1 else equity
        if (
            daily_usd >= config.max_daily_loss_usd
            or daily >= Decimal("0.02")
            or weekly >= Decimal("0.05")
            or drawdown >= Decimal("0.10")
        ):
            raise LiveBlocked("A daily, weekly or drawdown loss limit has been reached")
        state = PortfolioState(
            equity,
            {
                bucket: sum(exposures.values(), Decimal(0)) if bucket == BUCKET else Decimal(0)
                for bucket in Bucket
            },
            exposures,
            len(exposures),
        )
        return venue, execution, balances, EquityAssessment(state, daily, weekly, drawdown)

    async def latch(self, reason):
        async with self.sessions.begin() as db:
            config = await db.get(LiveControlRow, 1, with_for_update=True)
            if config is not None:
                changed = config.state != "BLOCKED" or config.reason != reason
                config.state, config.reason = "BLOCKED", reason
                if changed:
                    audit(db, "LIVE_EXECUTION_BLOCKED", config.owner_id)

    async def refresh(self):
        config = await self.configuration()
        if config is None or not config.initialized:
            return
        try:
            async with self.serialized():
                config = await self.configuration()
                await self._sync(config)
            self._transient_failures = 0
        except LiveBlocked as exc:
            if "being reconciled" not in str(exc):
                await self.latch(str(exc))
        except TransientExchangeError as exc:
            self._transient_failures += 1
            if self._transient_failures >= TRANSIENT_FAILURES_BEFORE_BLOCK:
                await self.latch(str(exc))
        except ExchangePrivateError as exc:
            await self.latch(str(exc))
        except Exception:
            await self.latch("Real account synchronization failed; no new trades are allowed")

    async def execute(self, row, owner_id, approved_version):
        try:
            async with self.serialized():
                config = await self.configuration(owner_id)
                async with self.sessions() as db:
                    control = await db.get(ControlRow, 1)
                if (
                    not self.capable()
                    or config is None
                    or not config.enabled
                    or config.state != "READY"
                    or config.version != approved_version
                    or control is None
                    or control.environment != Environment.LIVE
                    or control.status != Status.RUNNING
                ):
                    raise LiveBlocked("Real trading is not active and ready")
                if is_proposal_expired(row, self.clock.now()):
                    return ProposalExecutionResult(
                        ProposalExecutionStatus.EXPIRED, None, ("Proposal expired",)
                    )
                venue, execution, balances, equity = await self._sync(config)
                if row.venue != venue.name:
                    raise LiveBlocked(
                        "This proposal was analysed for another exchange than the real account"
                    )
                if row.base not in venue.assets or row.quote != venue.cash:
                    raise LiveBlocked("The real account cannot trade this pair")
                now = self.clock.now()
                async with self.sessions() as db:
                    mandate = await db.get(AiAutonomyControlRow, 1)
                if mandate is None:
                    raise LiveBlocked("Operator allocation mandate is unavailable")
                policy = replace(
                    PORTFOLIO_POLICY,
                    bucket_targets={
                        Bucket.CORE: mandate.target_core_pct,
                        Bucket.GROWTH: mandate.target_growth_pct,
                        Bucket.SPECULATIVE: mandate.target_speculative_pct,
                    },
                )
                try:
                    outcome = await _revalidate(
                        self.sessions,
                        venue.market,
                        row,
                        account_id(config),
                        now,
                        True,
                        equity,
                        policy,
                    )
                except LookupError:
                    # Nothing reached the exchange: refuse this proposal, keep LIVE armed.
                    raise LiveBlocked(
                        "Proposal instrument is not available for real trading"
                    ) from None
                async with self.sessions.begin() as db:
                    await ShadowDecisionRepository(db).save(outcome)
                risk = outcome.risk_assessment
                if (
                    not outcome.allocation_approved
                    or risk is None
                    or risk.decision == RiskDecision.REJECTED
                ):
                    return ProposalExecutionResult(
                        "BLOCKED", None, risk.reasons if risk else outcome.allocation_reasons
                    )
                instrument = outcome.proposal.instrument
                snapshot = await venue.market.fetch_snapshot(instrument)
                if (
                    not trustworthy_mark(snapshot, instrument, self.clock.now())
                    or instrument.price_increment is None
                    or instrument.quantity_increment is None
                    or instrument.min_quantity is None
                ):
                    raise LiveBlocked("Current price or instrument precision is unavailable")
                buy = outcome.proposal.direction == TradeDirection.LONG
                reference = snapshot.ask if buy else snapshot.bid
                if abs(reference / row.entry_price - 1) > config.slippage_pct:
                    raise LiveBlocked("Price moved beyond the approved slippage limit")
                increment = instrument.price_increment
                bound = reference * (1 + config.slippage_pct if buy else 1 - config.slippage_pct)
                price = (bound / increment).to_integral_value(
                    rounding=ROUND_DOWN if buy else ROUND_UP
                ) * increment
                minimum_cost = await venue.minimum_notional(instrument)
                _, fee_transport = await self.account(config)
                fee_rate = await venue.fee_rate(fee_transport, instrument)
                if not fee_rate.is_finite() or not 0 <= fee_rate <= Decimal("0.10"):
                    raise LiveBlocked("Trading fee cannot be verified")
                cash = balances.get(venue.cash, (Decimal(0), Decimal(0)))[1]
                held = balances.get(instrument.base, (Decimal(0), Decimal(0)))[1]
                quantity = min(
                    risk.final_quantity,
                    config.max_order_usd / (price * (1 + fee_rate if buy else 1)),
                )
                exposure = sum(equity.portfolio_state.asset_exposure.values(), Decimal(0))
                quantity = (
                    min(
                        quantity,
                        cash / (price * (1 + fee_rate)),
                        max(config.max_total_usd - exposure, Decimal(0)) / price,
                    )
                    if buy
                    else min(quantity, held)
                )
                quantity = (quantity / instrument.quantity_increment).to_integral_value(
                    rounding=ROUND_DOWN
                ) * instrument.quantity_increment
                if quantity < instrument.min_quantity or quantity * price < minimum_cost:
                    raise LiveBlocked(
                        "Approved quantity is below venue minimums or available account limits"
                    )
                try:
                    levels = await venue.book(instrument, buy, self.clock.now())
                except InvalidBookEvidence:
                    raise LiveBlocked("Invalid order book evidence") from None
                available_at_limit = Decimal(0)
                for level_price, level_quantity in levels:
                    if level_price <= price if buy else level_price >= price:
                        available_at_limit += level_quantity
                if available_at_limit < quantity:
                    raise LiveBlocked("Insufficient order book liquidity within the price limit")
                if is_proposal_expired(row, self.clock.now()):
                    raise LiveBlocked("Proposal expired during revalidation")
                # Recheck price age and the proposal's owner/one-use approval immediately
                # before creating the durable intent; lengthy fee/book calls can go stale.
                if not trustworthy_mark(snapshot, instrument, self.clock.now()):
                    raise LiveBlocked("Quote expired during revalidation")
                async with self.sessions() as db:
                    from wallybot.infrastructure.models import TradeProposalRow

                    approved = await db.get(TradeProposalRow, row.proposal_id)
                if (
                    approved is None
                    or approved.owner_id != owner_id
                    or approved.decision_status != "APPROVED"
                    or approved.execution_environment != "LIVE"
                ):
                    raise LiveBlocked("A committed operator-owned LIVE approval is required")
                client_id = str(uuid4())
                intent = OrderIntent(
                    account_id(config),
                    "LIVE",
                    instrument,
                    Side.BUY if buy else Side.SELL,
                    OrderKind.LIMIT,
                    quantity,
                    price,
                    str(uuid4()),
                    client_id,
                    "proposal:" + row.proposal_id,
                    str(uuid4()),
                    {"risk": 1, "live": config.version, "mandate": mandate_version(mandate)},
                    self.clock.now(),
                    min(
                        risk.expires_at,
                        snapshot.timestamp + timedelta(seconds=60),
                        row.as_of + timedelta(seconds=float(row.signal_ttl_seconds)),
                    ),
                    OrderStatus.VALIDATED,
                )
                status = await execution.submit(intent)
                if status not in TERMINAL_STATUSES:
                    await self.latch("Submitted order requires reconciliation before another trade")
                return ProposalExecutionResult(status.value, client_id, risk.reasons)
        except LiveBlocked as exc:
            return ProposalExecutionResult("BLOCKED", None, (str(exc),))
        except Exception:
            await self.latch("Real execution failed; reconcile before rearming")
            return ProposalExecutionResult(
                "FAILED", None, ("Real execution failed; reconcile before rearming",)
            )
