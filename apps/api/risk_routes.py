"""Persistent circuit breaker state -- RISK.md: "hard loss/drawdown, ambiguity and reconciliation
breakers require operator acknowledgment with fresh MFA." `Admin` already enforces fresh MFA
(within the configured window) for every action on this router, same as `/api/control` and
`/api/portfolio/fund`; there is no separate re-entry step here.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import BreakerListView, BreakerView, RiskLimitsView
from apps.api.portfolio_routes import paper_account_id
from wallybot.application.decision_loop import RISK_POLICY
from wallybot.domain.breaker import BreakerType, breakers_to_trip
from wallybot.domain.equity import compute_daily_loss, compute_drawdown, compute_weekly_loss
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/risk", tags=["risk"])

# Covers both the daily (24h) and weekly (7d) boundary lookups with one bounded query -- same
# window `wallybot.application.equity_tracker.assess_equity` uses for the live decision tick.
_HISTORY_WINDOW = timedelta(days=8)


def _view(breaker) -> BreakerView:
    return BreakerView(
        breaker_type=breaker.breaker_type.value,
        reason=breaker.reason,
        tripped_at=breaker.tripped_at.isoformat(),
        cleared_at=breaker.cleared_at.isoformat() if breaker.cleared_at else None,
        cleared_by=breaker.cleared_by,
    )


@router.get("/limits", response_model=RiskLimitsView)
async def risk_limits(request: Request, user: SignedIn) -> RiskLimitsView:
    """RISK_POLICY's configured limits alongside this account's current consumption and breach
    state -- reads the latest `EquitySnapshot` the decision loop already recorded rather than
    re-pricing positions itself, so this stays a read-only view with no market-data dependency.
    "As of" the last decision tick, not a live repricing -- never fabricates a fresher number than
    what was actually computed.
    """
    account_id = paper_account_id(user.id)
    now = datetime.now(UTC)
    async with request.app.state.sessions() as db:
        repo = EquitySnapshotRepository(db)
        latest = await repo.latest(account_id, "PAPER")
        history = await repo.recent(account_id, "PAPER", now - _HISTORY_WINDOW)

    if latest is None:
        return RiskLimitsView(
            policy_version=RISK_POLICY.version,
            max_daily_loss=str(RISK_POLICY.max_daily_loss),
            max_weekly_loss=str(RISK_POLICY.max_weekly_loss),
            max_drawdown=str(RISK_POLICY.max_drawdown),
            as_of=None,
            equity=None,
            high_water_mark=None,
            daily_loss=None,
            weekly_loss=None,
            drawdown=None,
            daily_loss_breached=False,
            weekly_loss_breached=False,
            drawdown_breached=False,
        )

    daily_loss = compute_daily_loss(history, latest.equity, now)
    weekly_loss = compute_weekly_loss(history, latest.equity, now)
    drawdown = compute_drawdown(latest.equity, latest.high_water_mark)
    trips = {
        breaker_type
        for breaker_type, _ in breakers_to_trip(
            daily_loss, weekly_loss, drawdown, RISK_POLICY, reconciliation_healthy=True
        )
    }
    return RiskLimitsView(
        policy_version=RISK_POLICY.version,
        max_daily_loss=str(RISK_POLICY.max_daily_loss),
        max_weekly_loss=str(RISK_POLICY.max_weekly_loss),
        max_drawdown=str(RISK_POLICY.max_drawdown),
        as_of=latest.recorded_at.isoformat(),
        equity=str(latest.equity),
        high_water_mark=str(latest.high_water_mark),
        daily_loss=str(daily_loss),
        weekly_loss=str(weekly_loss),
        drawdown=str(drawdown),
        daily_loss_breached=BreakerType.DAILY_LOSS in trips,
        weekly_loss_breached=BreakerType.WEEKLY_LOSS in trips,
        drawdown_breached=BreakerType.DRAWDOWN in trips,
    )


@router.get("/breakers", response_model=BreakerListView)
async def list_breakers(request: Request, user: SignedIn) -> BreakerListView:
    async with request.app.state.sessions() as db:
        rows = await BreakerRepository(db).list_all()
    return BreakerListView(rows=[_view(row) for row in rows])


@router.post("/breakers/{breaker_type}/clear", response_model=BreakerView)
async def clear_breaker(breaker_type: str, request: Request, user: Admin) -> BreakerView:
    try:
        parsed_type = BreakerType(breaker_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown breaker type") from exc

    now = datetime.now(UTC)
    async with request.app.state.sessions.begin() as db:
        cleared = await BreakerRepository(db).clear(parsed_type, user.id, now)
        if not cleared:
            raise HTTPException(status_code=409, detail="Breaker is not currently active")
        audit(db, "BREAKER_CLEARED", user.id)

    async with request.app.state.sessions() as db:
        rows = await BreakerRepository(db).list_all()
    cleared_row = next(row for row in rows if row.breaker_type is parsed_type)
    return _view(cleared_row)
