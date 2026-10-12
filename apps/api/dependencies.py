import hmac
import time
from typing import Annotated

from fastapi import Depends, Request

from wallybot.security.auth import AuthError, Identity


async def identity(request: Request) -> Identity:
    settings = request.app.state.settings
    raw = request.cookies.get(settings.cookie_name, "")
    if not raw:
        raise AuthError("Authentication required")
    return await request.app.state.auth.identity(raw)


SignedIn = Annotated[Identity, Depends(identity)]


async def csrf(request: Request, user: SignedIn) -> Identity:
    settings = request.app.state.settings
    raw = request.cookies.get(settings.cookie_name, "")
    expected = request.app.state.auth.crypto.csrf(raw)
    if not hmac.compare_digest(request.headers.get("x-csrf-token", "").encode(), expected.encode()):
        raise AuthError("Invalid CSRF token", 403)
    return user


Protected = Annotated[Identity, Depends(csrf)]

# SECURITY.md: "Require recent MFA for secret changes, risk edits, LIVE activation, resumption
# from a breaker and destructive emergency commands."
MFA_RECENCY_SECONDS = 300


async def admin(request: Request, user: Protected) -> Identity:
    if user.role != "ADMIN":
        raise AuthError("Administrator required", 403)
    if user.mfa_at + MFA_RECENCY_SECONDS <= int(time.time()):
        raise AuthError("Sign in again with MFA to confirm this action", 403)
    await request.app.state.throttle.check("control:" + user.id)
    return user


Admin = Annotated[Identity, Depends(admin)]


async def fresh_mfa(user: Protected) -> Identity:
    """Same recent-MFA requirement `admin()` enforces, without the ADMIN role restriction -- a
    VIEWER changing their own password or TOTP is a "secret change" too (SECURITY.md), but not an
    administrative action; role has nothing to do with whether the session proved MFA recently.
    """
    if user.mfa_at + MFA_RECENCY_SECONDS <= int(time.time()):
        raise AuthError("Sign in again with MFA to confirm this action", 403)
    return user


FreshMfa = Annotated[Identity, Depends(fresh_mfa)]


async def auth_throttle(request: Request) -> None:
    # No trust in client-supplied forwarding headers. Gateway provides a shared limit in addition.
    peer = request.client.host if request.client else "unknown"
    await request.app.state.throttle.check("peer:" + peer)
