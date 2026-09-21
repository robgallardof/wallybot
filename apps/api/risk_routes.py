"""Persistent circuit breaker state -- RISK.md: "hard loss/drawdown, ambiguity and reconciliation
breakers require operator acknowledgment with fresh MFA." `Admin` already enforces fresh MFA
(within the configured window) for every action on this router, same as `/api/control` and
`/api/portfolio/fund`; there is no separate re-entry step here.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from apps.api.dependencies import Admin, SignedIn
from apps.api.dto import BreakerListView, BreakerView
from wallybot.domain.breaker import BreakerType
from wallybot.infrastructure.breaker_repository import BreakerRepository
from wallybot.security.auth import audit

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _view(breaker) -> BreakerView:
    return BreakerView(
        breaker_type=breaker.breaker_type.value,
        reason=breaker.reason,
        tripped_at=breaker.tripped_at.isoformat(),
        cleared_at=breaker.cleared_at.isoformat() if breaker.cleared_at else None,
        cleared_by=breaker.cleared_by,
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
