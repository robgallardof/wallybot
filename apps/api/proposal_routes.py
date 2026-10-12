"""Proposal history plus the MFA-protected operator decisions (ADR-017).

An approval is single-use and committed first. Only then, and only while the operator has
explicitly enabled PAPER or LIVE, the selected account service re-reads market data and re-runs
the deterministic allocator/risk gate before an order can exist. LIVE additionally binds the
displayed limits version and rechecks private balances. Telegram and the AI worker never execute.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import (
    ProposalExecutionView,
    ProposalSimulationView,
    TradeProposalListView,
    TradeProposalView,
)
from wallybot.application.notification_dispatch import dispatch_telegram_notification
from wallybot.application.paper_accounts import paper_ai_account_id
from wallybot.application.proposal_execution import (
    ProposalExecutionResult,
    ProposalExecutionStatus,
    execute_approved_proposal,
    is_proposal_expired,
    proposal_expires_at,
    simulate_proposal,
)
from wallybot.domain.control import Environment
from wallybot.domain.market import MarketDataProvider
from wallybot.domain.trade_proposal import TradeDirection
from wallybot.infrastructure.models import ControlRow, ShadowDecisionRow, TradeProposalRow
from wallybot.notifications.telegram import Notification, NotificationSeverity
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


class ProposalDecisionInput(BaseModel):
    environment: Environment | None = None
    live_version: int | None = None


def _decision_notification(
    row: TradeProposalRow, status: str, execution: ProposalExecutionResult | None
) -> Notification:
    action = "BUY / Comprar" if row.direction == TradeDirection.LONG else "SELL / Vender"
    if status == "APPROVED":
        title = "WallyBot proposal approved / Propuesta aprobada"
        if execution is not None and execution.client_order_id is not None:
            outcome = (
                f"{row.execution_environment or 'PAPER'} order {execution.status} / "
                f"Orden {row.execution_environment or 'PAPER'} {execution.status}"
            )
        else:
            outcome = "No order was created / No se creó ninguna orden"
            if execution is not None:
                outcome += f" ({execution.status})"
    else:
        title = "WallyBot proposal rejected / Propuesta rechazada"
        outcome = "No order was created / No se creó ninguna orden"
    return Notification(
        NotificationSeverity.INFO,
        title,
        f"{action} {row.base}/{row.quote} at {row.entry_price}.\n{outcome}.\n"
        "Telegram cannot execute this decision / Telegram no puede ejecutar esta decisión.",
    )


def _provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_overview.keywords["provider"]


async def _execute(
    row: TradeProposalRow, request: Request, user_id: str, approved_version: int | None = None
) -> ProposalExecutionResult:
    """Revalidate after the committed approval; a failure is recorded, never retried."""
    async with request.app.state.sessions() as db:
        control = await db.get(ControlRow, 1)
    if control is not None and control.environment != row.execution_environment:
        return ProposalExecutionResult("BLOCKED", None, ("Execution mode changed after approval",))
    if control is not None and control.environment == Environment.LIVE:
        return await request.app.state.live_trading.execute(row, user_id, approved_version)
    if control is None or control.environment != Environment.PAPER:
        return ProposalExecutionResult(
            ProposalExecutionStatus.OBSERVE_ONLY,
            None,
            ("PAPER is disabled; the approval was recorded without an order",),
        )
    try:
        return await execute_approved_proposal(
            request.app.state.sessions,
            _provider(request),
            request.app.state.paper_ai,
            request.app.state.id_generator,
            row,
            paper_ai_account_id(user_id),
            datetime.now(UTC),
        )
    except Exception as exc:  # noqa: BLE001 -- fail closed and keep the reason auditable
        return ProposalExecutionResult(
            ProposalExecutionStatus.FAILED, None, (f"revalidation failed: {type(exc).__name__}",)
        )


async def _pending_row(request: Request, proposal_id: str, user_id: str) -> TradeProposalRow:
    async with request.app.state.sessions() as db:
        row = await db.get(TradeProposalRow, proposal_id)
    if row is None or row.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if row.decision_status != "PENDING":
        raise HTTPException(status_code=409, detail="Proposal was already decided")
    return row


@router.post("/{proposal_id}/{decision}")
async def decide_proposal(
    proposal_id: str,
    decision: str,
    request: Request,
    user: Admin,
    body: ProposalDecisionInput | None = None,
) -> dict[str, str | None]:
    """Record one operator decision, bound to the current PAPER/OBSERVE/LIVE mode."""
    if decision not in {"simulate", "approve", "reject"}:
        raise HTTPException(status_code=404, detail="Unknown proposal decision")
    status = {"simulate": "SIMULATED", "approve": "APPROVED", "reject": "REJECTED"}[decision]
    if decision == "simulate":
        async with request.app.state.sessions() as db:
            control = await db.get(ControlRow, 1)
        if control is None or control.environment != Environment.PAPER:
            raise HTTPException(
                status_code=409,
                detail="Simulations are disabled. Enable PAPER explicitly in Settings first.",
            )
        row = await _pending_row(request, proposal_id, user.id)
        if is_proposal_expired(row, datetime.now(UTC)):
            raise HTTPException(status_code=409, detail="Proposal expired")
        # Market reads and the simulation write never run while holding the proposal-row lock.
        try:
            await simulate_proposal(
                request.app.state.sessions,
                _provider(request),
                row,
                paper_ai_account_id(user.id),
                datetime.now(UTC),
            )
        except LookupError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        async with request.app.state.sessions.begin() as db:
            audit(db, "AI_PROPOSAL_SIMULATED", user.id)
        # Simulation is evidence, not an approval. The proposal remains actionable.
        return {"proposal_id": proposal_id, "status": status, "execution_status": None}

    async with request.app.state.sessions.begin() as db:
        control = await db.get(ControlRow, 1, with_for_update=True)
        if decision == "approve" and control is not None:
            if (
                body is not None
                and body.environment is not None
                and body.environment != control.environment
            ):
                raise HTTPException(409, "Execution mode changed; review the proposal again")
            if control.environment == Environment.LIVE:
                from wallybot.infrastructure.live_models import LiveControlRow

                live = await db.get(LiveControlRow, 1)
                if (
                    body is None
                    or body.environment != Environment.LIVE
                    or live is None
                    or body.live_version != live.version
                    or live.owner_id != user.id
                ):
                    raise HTTPException(
                        409, "Explicit LIVE approval with current limits is required"
                    )
        row = await db.get(TradeProposalRow, proposal_id, with_for_update=True)
        if row is None or row.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if row.decision_status != "PENDING":
            raise HTTPException(status_code=409, detail="Proposal was already decided")
        if decision == "approve" and is_proposal_expired(row, datetime.now(UTC)):
            raise HTTPException(status_code=409, detail="Proposal expired")
        row.decision_status = status
        if decision == "approve":
            row.execution_environment = control.environment if control else Environment.OBSERVE
        row.decided_at = datetime.now(UTC)
        audit(db, f"AI_PROPOSAL_{status}", user.id)

    execution = None
    if decision == "approve":
        execution = await _execute(row, request, user.id, body.live_version if body else None)
        async with request.app.state.sessions.begin() as db:
            stored = await db.get(TradeProposalRow, proposal_id, with_for_update=True)
            if stored is not None:
                stored.execution_status = execution.status
                stored.execution_order_id = execution.client_order_id
                stored.execution_reasons = list(execution.reasons)
            audit(db, f"AI_PROPOSAL_EXECUTION_{execution.status}", user.id)

    await dispatch_telegram_notification(
        request.app.state.sessions,
        request.app.state.auth.crypto,
        request.app.state.telegram_transport,
        _decision_notification(row, status, execution),
        request.app.state.notification_throttle,
        datetime.now(UTC),
    )
    return {
        "proposal_id": proposal_id,
        "status": status,
        "execution_status": execution.status if execution is not None else None,
    }


@router.get("", response_model=TradeProposalListView)
async def list_proposals(request: Request, user: SignedIn) -> TradeProposalListView:
    """Return proposal evidence only; this endpoint cannot approve, execute or transfer funds."""
    async with request.app.state.sessions() as db:
        rows = (
            await db.scalars(
                select(TradeProposalRow)
                .where(TradeProposalRow.owner_id == user.id)
                .order_by(TradeProposalRow.as_of.desc())
                .limit(100)
            )
        ).all()
        simulations = []
        if rows:
            simulations = (
                await db.scalars(
                    select(ShadowDecisionRow)
                    .where(ShadowDecisionRow.proposal_id.in_([row.proposal_id for row in rows]))
                    .order_by(ShadowDecisionRow.as_of.desc())
                )
            ).all()
    simulation_by_proposal = {}
    for result in simulations:
        simulation_by_proposal.setdefault(result.proposal_id, result)
    return TradeProposalListView(
        rows=[
            TradeProposalView(
                proposal_id=row.proposal_id,
                venue=row.venue,
                base=row.base,
                quote=row.quote,
                direction=row.direction,
                confidence=str(row.confidence),
                suggested_allocation_pct=str(row.suggested_allocation_pct),
                entry_price=str(row.entry_price),
                stop_price=str(row.stop_price) if row.stop_price is not None else None,
                take_profit_price=str(row.take_profit_price)
                if row.take_profit_price is not None
                else None,
                reasons=[str(value) for value in row.reasons],
                risks=[str(value) for value in row.risks],
                model_id=row.model_id,
                as_of=row.as_of.isoformat(),
                expires_at=proposal_expires_at(row).isoformat(),
                decision_status=row.decision_status,
                decided_at=row.decided_at.isoformat() if row.decided_at else None,
                simulation=(
                    ProposalSimulationView(
                        allocation_approved=result.allocation_approved,
                        risk_decision=result.risk_decision,
                        reasons=(result.risk_reasons or result.allocation_reasons),
                        simulated_at=result.as_of.isoformat(),
                    )
                    if (result := simulation_by_proposal.get(row.proposal_id)) is not None
                    else None
                ),
                execution=(
                    ProposalExecutionView(
                        environment=row.execution_environment or "PAPER",
                        status=row.execution_status,
                        client_order_id=row.execution_order_id,
                        reasons=[str(value) for value in row.execution_reasons or []],
                    )
                    if row.execution_status is not None
                    else None
                ),
            )
            for row in rows
        ]
    )
