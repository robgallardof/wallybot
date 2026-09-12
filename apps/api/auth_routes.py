from fastapi import APIRouter, Depends, Request, Response

from apps.api.dependencies import Protected, SignedIn, auth_throttle
from apps.api.schemas import Login, SetupFinish, SetupStart, Verification
from wallybot.infrastructure.models import ControlRow

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def set_cookie(request: Request, response: Response, raw: str) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        settings.cookie_name,
        raw,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_absolute_seconds,
    )


@router.get("/setup-status")
async def setup_status(request: Request) -> dict[str, bool]:
    async with request.app.state.sessions() as db:
        state = await db.get(ControlRow, 1)
        return {"setup_required": state is not None and not state.setup_complete}


@router.post("/setup/start", dependencies=[Depends(auth_throttle)])
async def setup_start(body: SetupStart, request: Request) -> dict[str, str]:
    return await request.app.state.auth.setup_start(
        body.bootstrap_token, body.username, body.password
    )


@router.post("/setup/finish", dependencies=[Depends(auth_throttle)])
async def setup_finish(
    body: SetupFinish, request: Request, response: Response
) -> dict[str, object]:
    raw, recovery = await request.app.state.auth.setup_finish(
        body.bootstrap_token, body.challenge, body.code
    )
    set_cookie(request, response, raw)
    return {"recovery_codes": recovery, "csrf": request.app.state.auth.crypto.csrf(raw)}


@router.post("/login", dependencies=[Depends(auth_throttle)])
async def login(body: Login, request: Request) -> dict[str, str]:
    await request.app.state.throttle.check("username:" + body.username)
    return {"challenge": await request.app.state.auth.login(body.username, body.password)}


@router.post("/mfa", dependencies=[Depends(auth_throttle)])
async def mfa(body: Verification, request: Request, response: Response) -> dict[str, str]:
    await request.app.state.throttle.check("challenge:" + body.challenge)
    raw = await request.app.state.auth.mfa(body.challenge, body.code)
    set_cookie(request, response, raw)
    return {"csrf": request.app.state.auth.crypto.csrf(raw)}


@router.get("/me")
async def me(request: Request, user: SignedIn) -> dict[str, object]:
    raw = request.cookies[request.app.state.settings.cookie_name]
    return {
        "username": user.username,
        "role": user.role,
        "csrf": request.app.state.auth.crypto.csrf(raw),
    }


@router.post("/logout")
async def logout(request: Request, response: Response, user: Protected) -> dict[str, bool]:
    settings = request.app.state.settings
    await request.app.state.auth.logout(request.cookies[settings.cookie_name], user.id)
    response.delete_cookie(
        settings.cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
    return {"ok": True}
