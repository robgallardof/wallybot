"""A pending confirmation for a sensitive Telegram-originated command.

RISK.md: "Confirmar acciones sensibles con tokens expiran/anti-replay y MFA web cuando
corresponda." SECURITY.md: "Sensitive commands require confirmation and a step-up web flow where
appropriate." A Telegram command never executes a sensitive action by itself -- `/pause`/`/resume`
only create a `TelegramConfirmation` here; the operator must confirm it through the existing
Admin+fresh-MFA web flow (`apps/api/dependencies.py`'s `admin()`), the same authorization every
other sensitive action on this system already requires. Telegram itself never gains execution
capability, matching this codebase's "no execution/withdrawal capability for anything but the
authenticated web session" boundary.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

CONFIRMATION_TTL = timedelta(minutes=5)


class TelegramAction(StrEnum):
    PAUSE = "PAUSE"
    RESUME = "RESUME"


@dataclass(frozen=True)
class TelegramConfirmation:
    confirmation_id: str
    action: TelegramAction
    requested_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None = None
    confirmed_by: str | None = None

    def __post_init__(self) -> None:
        if self.expires_at <= self.requested_at:
            raise ValueError("expires_at must be after requested_at")
        if self.confirmed_at is not None and self.confirmed_at < self.requested_at:
            raise ValueError("confirmed_at cannot be before requested_at")

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    @property
    def is_pending(self) -> bool:
        return not self.is_confirmed
