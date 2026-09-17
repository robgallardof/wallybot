from fastapi import APIRouter, Depends, Request, Response

from apps.api.cookies import clear_cookie, set_cookie
from apps.api.dependencies import Protected, SignedIn, auth_throttle
from apps.api.dto import (
    ChallengeView,
    CsrfView,
    LogoutView,
    MeView,
    SetupFinishView,
    SetupStartView,
    SetupStatusView,
)
from apps.api.schemas import Login, MfaConfirm, SetupFinish, SetupStart, Verification
from wallybot.infrastructure.models import ControlRow

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/setup-status", response_model=SetupStatusView)
async def setup_status(request: Request) -> SetupStatusView:
    async with request.app.state.sessions() as db:
        state = await db.get(ControlRow, 1)
        return SetupStatusView(setup_required=state is not None and not state.setup_complete)


@router.post("/setup/start", dependencies=[Depends(auth_throttle)], response_model=SetupStartView)
async def setup_start(body: SetupStart, request: Request) -> SetupStartView:
    result = await request.app.state.auth.setup_start(
        body.bootstrap_token, body.username, body.password
    )
    return SetupStartView(**result)


@router.post("/setup/finish", dependencies=[Depends(auth_throttle)], response_model=SetupFinishView)
async def setup_finish(
    body: SetupFinish, request: Request, response: Response
) -> SetupFinishView:
    raw, recovery = await request.app.state.auth.setup_finish(
        body.bootstrap_token, body.challenge, body.code
    )
    set_cookie(request, response, raw)
    return SetupFinishView(recovery_codes=recovery, csrf=request.app.state.auth.crypto.csrf(raw))


@router.post("/login", dependencies=[Depends(auth_throttle)], response_model=ChallengeView)
async def login(body: Login, request: Request) -> ChallengeView:
    await request.app.state.throttle.check("username:" + body.username)
    return ChallengeView(challenge=await request.app.state.auth.login(body.username, body.password))


@router.post("/mfa", dependencies=[Depends(auth_throttle)], response_model=CsrfView)
async def mfa(body: Verification, request: Request, response: Response) -> CsrfView:
    await request.app.state.throttle.check("challenge:" + body.challenge)
    raw = await request.app.state.auth.mfa(body.challenge, body.code)
    set_cookie(request, response, raw)
    return CsrfView(csrf=request.app.state.auth.crypto.csrf(raw))


@router.get("/me", response_model=MeView)
async def me(request: Request, user: SignedIn) -> MeView:
    raw = request.cookies[request.app.state.settings.cookie_name]
    return MeView(
        username=user.username,
        role=user.role,
        csrf=request.app.state.auth.crypto.csrf(raw),
    )


@router.post("/logout", response_model=LogoutView)
async def logout(request: Request, response: Response, user: Protected) -> LogoutView:
    settings = request.app.state.settings
    await request.app.state.auth.logout(request.cookies[settings.cookie_name], user.id)
    clear_cookie(request, response)
    return LogoutView(ok=True)


@router.post("/confirm-mfa", dependencies=[Depends(auth_throttle)], response_model=LogoutView)
async def confirm_mfa(body: MfaConfirm, request: Request, user: Protected) -> LogoutView:
    """Refreshes the signed-in session's MFA recency (see `AuthService.confirm_mfa`) so an Admin
    action past the 5-minute window (`apps/api/dependencies.py`'s `admin()`) can succeed again
    without a full logout/login -- no cookie changes, the session and its CSRF secret are
    untouched."""
    await request.app.state.throttle.check("confirm-mfa:" + user.id)
    settings = request.app.state.settings
    await request.app.state.auth.confirm_mfa(request.cookies[settings.cookie_name], body.code)
    return LogoutView(ok=True)
