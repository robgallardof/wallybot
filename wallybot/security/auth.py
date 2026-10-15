import hmac
import time
from dataclasses import dataclass
from uuid import uuid4

import pyotp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.concurrency import run_in_threadpool

from wallybot.infrastructure.models import (
    ChallengeRow,
    ControlRow,
    EventRow,
    RecoveryRow,
    SessionRow,
    UserRow,
)
from wallybot.infrastructure.settings import Settings
from wallybot.security.crypto import Crypto, digest, matching_step, token


class AuthError(Exception):
    def __init__(self, message: str = "Invalid credentials", status: int = 401) -> None:
        self.message = message
        self.status = status


@dataclass(frozen=True)
class Identity:
    id: str
    username: str
    role: str
    mfa_at: int


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    created_at: int
    last_seen: int
    expires_at: int
    is_current: bool


def audit(
    db: AsyncSession, event: str, actor: str | None = None, message: str | None = None
) -> None:
    db.add(
        EventRow(
            id=str(uuid4()),
            timestamp=int(time.time()),
            actor=actor,
            event=event,
            message=message or event.replace("_", " ").lower(),
            correlation_id=str(uuid4()),
        )
    )


class AuthService:
    """Transactional identity adapter. Contains no portfolio or trading domain rules."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings
        self.crypto = Crypto(settings.encryption_key.get_secret_value())

    def bootstrap(self, supplied: str) -> None:
        if not hmac.compare_digest(
            supplied.encode(), self.settings.bootstrap_token.get_secret_value().encode()
        ):
            raise AuthError()

    async def failed(self, event: str) -> None:
        async with self.sessions.begin() as db:
            audit(db, event)

    async def setup_start(self, bootstrap: str, username: str, password: str) -> dict[str, str]:
        self.bootstrap(bootstrap)
        password_hash = await run_in_threadpool(self.crypto.passwords.hash, password)
        secret, challenge = pyotp.random_base32(), token()
        async with self.sessions.begin() as db:
            state = await db.get(ControlRow, 1, with_for_update=True)
            if state is None or state.setup_complete:
                raise AuthError("Setup is disabled", 409)
            # A new bootstrap attempt invalidates old enrollment material.
            await db.execute(delete(ChallengeRow).where(ChallengeRow.kind == "SETUP"))
            db.add(
                ChallengeRow(
                    token_hash=digest(challenge),
                    kind="SETUP",
                    username=username,
                    password_hash=password_hash,
                    totp_encrypted=self.crypto.encrypt(secret),
                    expires_at=int(time.time()) + 600,
                )
            )
        return {
            "challenge": challenge,
            "secret": secret,
            "uri": pyotp.TOTP(secret).provisioning_uri(username, issuer_name="WallyBot"),
        }

    async def setup_finish(
        self, bootstrap: str, challenge: str, code: str
    ) -> tuple[str, list[str]]:
        self.bootstrap(bootstrap)
        now = int(time.time())
        async with self.sessions.begin() as db:
            state = await db.get(ControlRow, 1, with_for_update=True)
            if state is None or state.setup_complete:
                raise AuthError("Setup is disabled", 409)
            pending = await db.get(ChallengeRow, digest(challenge), with_for_update=True)
            if pending is None or pending.kind != "SETUP" or pending.expires_at <= now:
                raise AuthError()
            if not pending.totp_encrypted or not pending.password_hash or not pending.username:
                raise AuthError("Invalid enrollment")
            step = matching_step(self.crypto.decrypt(pending.totp_encrypted), code, now)
            if step is None:
                raise AuthError("Invalid or expired verification code")
            user_id = str(uuid4())
            db.add(
                UserRow(
                    id=user_id,
                    username=pending.username,
                    password_hash=pending.password_hash,
                    totp_encrypted=pending.totp_encrypted,
                    last_totp_step=step,
                    role="ADMIN",
                    created_at=now,
                )
            )
            await db.flush()
            recovery = [token() for _ in range(8)]
            db.add_all([RecoveryRow(code_hash=digest(c), user_id=user_id) for c in recovery])
            state.setup_complete = True
            await db.delete(pending)
            session_token = self.new_session(db, user_id, now)
            audit(db, "ADMIN_CREATED", user_id)
            audit(db, "SESSION_CREATED", user_id)
        return session_token, recovery

    def new_session(self, db: AsyncSession, user_id: str, now: int) -> str:
        raw = token()
        db.add(
            SessionRow(
                token_hash=digest(raw),
                user_id=user_id,
                created_at=now,
                last_seen=now,
                expires_at=now + self.settings.session_absolute_seconds,
                mfa_at=now,
            )
        )
        return raw

    async def login(self, username: str, password: str) -> str:
        async with self.sessions.begin() as db:
            user = await db.scalar(select(UserRow).where(UserRow.username == username))
            stored = user.password_hash if user else self.crypto.dummy_hash
            valid = await run_in_threadpool(self.crypto.verify_password, stored, password)
            if not valid or user is None:
                raise AuthError()
            challenge = token()
            db.add(
                ChallengeRow(
                    token_hash=digest(challenge),
                    kind="LOGIN",
                    user_id=user.id,
                    expires_at=int(time.time()) + 300,
                )
            )
            return challenge

    async def mfa(self, challenge: str, code: str) -> str:
        now = int(time.time())
        async with self.sessions.begin() as db:
            pending = await db.get(ChallengeRow, digest(challenge), with_for_update=True)
            if pending is None or pending.kind != "LOGIN" or pending.expires_at <= now:
                raise AuthError()
            user = await db.get(UserRow, pending.user_id, with_for_update=True)
            if user is None:
                raise AuthError()
            step = matching_step(
                self.crypto.decrypt(user.totp_encrypted), code, now, user.last_totp_step
            )
            if step is None:
                recovery = await db.get(RecoveryRow, digest(code), with_for_update=True)
                if recovery is None or recovery.user_id != user.id:
                    raise AuthError("Invalid or already used verification code")
                await db.delete(recovery)
                # Recovery signs out all previous sessions.
                await db.execute(delete(SessionRow).where(SessionRow.user_id == user.id))
                audit(db, "RECOVERY_CODE_USED", user.id)
            else:
                user.last_totp_step = step
            await db.delete(pending)
            raw = self.new_session(db, user.id, now)
            audit(db, "SESSION_CREATED", user.id)
            return raw

    async def identity(self, raw: str) -> Identity:
        now = int(time.time())
        async with self.sessions.begin() as db:
            session = await db.get(SessionRow, digest(raw), with_for_update=True)
            if (
                session is None
                or session.expires_at <= now
                or session.last_seen + self.settings.session_idle_seconds <= now
            ):
                raise AuthError("Session expired")
            user = await db.get(UserRow, session.user_id)
            if user is None:
                raise AuthError()
            session.last_seen = now
            return Identity(user.id, user.username, user.role, session.mfa_at)

    async def confirm_mfa(self, raw: str, code: str) -> None:
        """Refreshes the *current* session's `mfa_at` after re-entering a valid TOTP code --
        without discarding the session or its CSRF secret, unlike `.mfa()` (which only ever runs
        during the login challenge, before a session exists at all). `admin()` in
        `apps/api/dependencies.py` requires `mfa_at` within the last 300 seconds for any
        Admin-gated action; without this, that requirement had no way to be satisfied again short
        of a full logout/login, making every admin action past the first 5 minutes of a session
        fail closed -- a real gap, not a hypothetical one.
        """
        now = int(time.time())
        async with self.sessions.begin() as db:
            session = await db.get(SessionRow, digest(raw), with_for_update=True)
            if (
                session is None
                or session.expires_at <= now
                or session.last_seen + self.settings.session_idle_seconds <= now
            ):
                raise AuthError("Session expired")
            user = await db.get(UserRow, session.user_id, with_for_update=True)
            if user is None:
                raise AuthError()
            step = matching_step(
                self.crypto.decrypt(user.totp_encrypted), code, now, user.last_totp_step
            )
            if step is None:
                raise AuthError("Invalid or expired verification code")
            user.last_totp_step = step
            session.mfa_at = now
            audit(db, "MFA_CONFIRMED", user.id)

    async def verify_totp(self, user_id: str, code: str) -> None:
        """Step-up for an out-of-band channel (the allowlisted Telegram chat): consumes one
        TOTP step exactly like `confirm_mfa`, so a code is never accepted twice anywhere."""
        now = int(time.time())
        async with self.sessions.begin() as db:
            user = await db.get(UserRow, user_id, with_for_update=True)
            if user is None or not user.totp_encrypted:
                raise AuthError()
            step = matching_step(
                self.crypto.decrypt(user.totp_encrypted), code, now, user.last_totp_step
            )
            if step is None:
                raise AuthError("Invalid or expired verification code")
            user.last_totp_step = step
            audit(db, "MFA_CONFIRMED_TELEGRAM", user.id)

    async def logout(self, raw: str, actor: str) -> None:
        async with self.sessions.begin() as db:
            await db.execute(delete(SessionRow).where(SessionRow.token_hash == digest(raw)))
            audit(db, "SESSION_REVOKED", actor)

    async def _current_session(self, db: AsyncSession, raw: str) -> SessionRow:
        now = int(time.time())
        session = await db.get(SessionRow, digest(raw), with_for_update=True)
        if (
            session is None
            or session.expires_at <= now
            or session.last_seen + self.settings.session_idle_seconds <= now
        ):
            raise AuthError("Session expired")
        return session

    async def change_password(self, raw: str, current_password: str, new_password: str) -> None:
        """SECURITY.md: "revoke on logout/password reset" -- every other session for this user is
        revoked, but not the one making this request, so the caller isn't immediately logged out
        by their own action."""
        async with self.sessions.begin() as db:
            session = await self._current_session(db, raw)
            user = await db.get(UserRow, session.user_id, with_for_update=True)
            if user is None:
                raise AuthError()
            valid = await run_in_threadpool(
                self.crypto.verify_password, user.password_hash, current_password
            )
            if not valid:
                raise AuthError("Current password is incorrect")
            user.password_hash = await run_in_threadpool(self.crypto.passwords.hash, new_password)
            await db.execute(
                delete(SessionRow).where(
                    SessionRow.user_id == user.id, SessionRow.token_hash != digest(raw)
                )
            )
            audit(db, "PASSWORD_CHANGED", user.id)

    async def replace_totp_start(self, raw: str) -> dict[str, str]:
        """Two-step, mirroring `setup_start`/`setup_finish`: the new secret only replaces the
        user's real one once `replace_totp_finish` proves it was enrolled correctly, so a typo'd
        QR scan can never lock an operator out of their own account."""
        now = int(time.time())
        async with self.sessions.begin() as db:
            session = await self._current_session(db, raw)
            user = await db.get(UserRow, session.user_id)
            if user is None:
                raise AuthError()
            username = user.username
            secret, challenge = pyotp.random_base32(), token()
            await db.execute(
                delete(ChallengeRow).where(
                    ChallengeRow.kind == "TOTP_REPLACE", ChallengeRow.user_id == user.id
                )
            )
            db.add(
                ChallengeRow(
                    token_hash=digest(challenge),
                    kind="TOTP_REPLACE",
                    user_id=user.id,
                    totp_encrypted=self.crypto.encrypt(secret),
                    expires_at=now + 600,
                )
            )
        return {
            "challenge": challenge,
            "secret": secret,
            "uri": pyotp.TOTP(secret).provisioning_uri(username, issuer_name="WallyBot"),
        }

    async def replace_totp_finish(self, raw: str, challenge: str, code: str) -> None:
        now = int(time.time())
        async with self.sessions.begin() as db:
            session = await self._current_session(db, raw)
            pending = await db.get(ChallengeRow, digest(challenge), with_for_update=True)
            if (
                pending is None
                or pending.kind != "TOTP_REPLACE"
                or pending.expires_at <= now
                or pending.user_id != session.user_id
            ):
                raise AuthError()
            if not pending.totp_encrypted:
                raise AuthError("Invalid enrollment")
            step = matching_step(self.crypto.decrypt(pending.totp_encrypted), code, now)
            if step is None:
                raise AuthError("Invalid or expired verification code")
            user = await db.get(UserRow, session.user_id, with_for_update=True)
            if user is None:
                raise AuthError()
            user.totp_encrypted = pending.totp_encrypted
            user.last_totp_step = step
            await db.delete(pending)
            session.mfa_at = now
            await db.execute(
                delete(SessionRow).where(
                    SessionRow.user_id == user.id, SessionRow.token_hash != digest(raw)
                )
            )
            audit(db, "TOTP_REPLACED", user.id)

    async def list_sessions(self, raw: str) -> list[SessionInfo]:
        async with self.sessions() as db:
            session = await self._current_session(db, raw)
            rows = (
                (
                    await db.execute(
                        select(SessionRow)
                        .where(SessionRow.user_id == session.user_id)
                        .order_by(SessionRow.last_seen.desc())
                    )
                )
                .scalars()
                .all()
            )
            current_hash = digest(raw)
            return [
                SessionInfo(
                    session_id=row.token_hash,
                    created_at=row.created_at,
                    last_seen=row.last_seen,
                    expires_at=row.expires_at,
                    is_current=row.token_hash == current_hash,
                )
                for row in rows
            ]

    async def revoke_session(self, actor_id: str, session_id: str) -> None:
        """Scoped to the caller's own sessions only (`user_id == actor_id`) -- there is no path
        here to revoke another user's session; that would need a real user-administration feature
        this codebase doesn't have yet."""
        async with self.sessions.begin() as db:
            row = await db.get(SessionRow, session_id, with_for_update=True)
            if row is None or row.user_id != actor_id:
                raise AuthError("Session not found", 404)
            await db.delete(row)
            audit(db, "SESSION_REVOKED", actor_id)
