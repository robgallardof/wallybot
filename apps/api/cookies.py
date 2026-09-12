"""Session cookie set/clear, centralized so both call sites always agree on attributes."""

from fastapi import Request, Response


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


def clear_cookie(request: Request, response: Response) -> None:
    settings = request.app.state.settings
    response.delete_cookie(
        settings.cookie_name, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
