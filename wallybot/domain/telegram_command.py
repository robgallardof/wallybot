"""Safe parsing and authorization of the deliberately small Telegram command surface.

Telegram is not an execution API.  It may expose read-only status/report requests once the
transport is configured, while every state-changing action remains a separate web/MFA flow.
"""

from dataclasses import dataclass
from enum import StrEnum


class TelegramCommandKind(StrEnum):
    STATUS = "status"
    REPORT = "report"


@dataclass(frozen=True)
class TelegramCommand:
    chat_id: int
    user_id: int
    kind: TelegramCommandKind


def parse_authorized_telegram_command(
    text: str,
    chat_id: int,
    user_id: int,
    allowed_chat_ids: frozenset[int],
    allowed_user_ids: frozenset[int],
) -> TelegramCommand | None:
    """Return only an allowlisted, exact, read-only command; reject all other input."""
    if chat_id not in allowed_chat_ids or user_id not in allowed_user_ids:
        return None
    normalized = text.strip().lower()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized not in {kind.value for kind in TelegramCommandKind}:
        return None
    return TelegramCommand(chat_id=chat_id, user_id=user_id, kind=TelegramCommandKind(normalized))
