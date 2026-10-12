from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response

from apps.api.cookies import clear_cookie, set_cookie
from apps.api.dependencies import FreshMfa, Protected, SignedIn, auth_throttle
from apps.api.dto import (
    ChallengeView,
    CsrfView,
    LogoutView,
    MeView,
    SessionListView,
    SessionView,
    SetupFinishView,
    SetupStartView,
    SetupStatusView,
)
from apps.api.schemas import (
    Login,
    MfaConfirm,
    PasswordChange,
    SetupFinish,
    SetupStart,
    Verification,
)
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
async def setup_finish(body: SetupFinish, request: Request, response: Response) -> SetupFinishView:
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
    return MeView.model_validate(
        {
            "username": user.username,
            "role": user.role,
            "csrf": request.app.state.auth.crypto.csrf(raw),
        }
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


@router.post("/password", dependencies=[Depends(auth_throttle)], response_model=LogoutView)
async def change_password(body: PasswordChange, request: Request, user: FreshMfa) -> LogoutView:
    """Requires a session with recent MFA (`FreshMfa`) plus re-entering the current password --
    the current-password check alone already exists in `AuthService.change_password`, but the
    recent-MFA gate additionally covers a session hijacked within the fresh-MFA window without the
    attacker knowing the password to begin with (SECURITY.md: "recent MFA for secret changes")."""
    settings = request.app.state.settings
    await request.app.state.auth.change_password(
        request.cookies[settings.cookie_name], body.current_password, body.new_password
    )
    return LogoutView(ok=True)


@router.post(
    "/totp/replace/start", dependencies=[Depends(auth_throttle)], response_model=SetupStartView
)
async def totp_replace_start(request: Request, user: FreshMfa) -> SetupStartView:
    settings = request.app.state.settings
    result = await request.app.state.auth.replace_totp_start(request.cookies[settings.cookie_name])
    return SetupStartView(**result)


@router.post(
    "/totp/replace/finish", dependencies=[Depends(auth_throttle)], response_model=LogoutView
)
async def totp_replace_finish(body: Verification, request: Request, user: Protected) -> LogoutView:
    settings = request.app.state.settings
    await request.app.state.auth.replace_totp_finish(
        request.cookies[settings.cookie_name], body.challenge, body.code
    )
    return LogoutView(ok=True)


@router.get("/sessions", response_model=SessionListView)
async def sessions(request: Request, user: SignedIn) -> SessionListView:
    settings = request.app.state.settings
    rows = await request.app.state.auth.list_sessions(request.cookies[settings.cookie_name])
    return SessionListView(
        rows=[
            SessionView(
                session_id=row.session_id,
                created_at=datetime.fromtimestamp(row.created_at, UTC).isoformat(),
                last_seen=datetime.fromtimestamp(row.last_seen, UTC).isoformat(),
                expires_at=datetime.fromtimestamp(row.expires_at, UTC).isoformat(),
                is_current=row.is_current,
            )
            for row in rows
        ]
    )


@router.delete("/sessions/{session_id}", response_model=LogoutView)
async def revoke_session(session_id: str, request: Request, user: Protected) -> LogoutView:
    """Scoped to the caller's own sessions only -- there is no route to another user's sessions
    yet, since this codebase has no broader user-administration feature to authorize that with."""
    await request.app.state.auth.revoke_session(user.id, session_id)
    return LogoutView(ok=True)
