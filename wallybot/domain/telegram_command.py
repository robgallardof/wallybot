"""Safe parsing and authorization of the deliberately small Telegram command surface.

Telegram is not an execution API.  It may expose read-only status/report requests once the
transport is configured, while every state-changing action remains a separate web/MFA flow.
"""

from dataclasses import dataclass
from enum import StrEnum


class TelegramCommandKind(StrEnum):
    """The complete, deliberately small set of recognized Telegram commands.

    :cvar STATUS: Request the current instance status.
    :cvar REPORT: Request the latest report.
    """

    STATUS = "status"
    REPORT = "report"


@dataclass(frozen=True)
class TelegramCommand:
    """A parsed, authorized, read-only Telegram command.

    :ivar chat_id: Telegram chat the command was sent from.
    :ivar user_id: Telegram user who sent it.
    :ivar kind: Which recognized command this is; see :class:`TelegramCommandKind`.
    """

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
    """Parse raw Telegram message text into a command, or reject it.

    Returns ``None`` (never partially trusts) unless the sender is on both allowlists and the
    text is an exact, case-insensitive match for a member of :class:`TelegramCommandKind` --
    optionally prefixed with ``/``. There is no execution command here by design.

    :param text: Raw message text as received from Telegram.
    :param chat_id: Chat the message was sent from.
    :param user_id: User who sent it.
    :param allowed_chat_ids: Chats permitted to issue commands.
    :param allowed_user_ids: Users permitted to issue commands.
    :returns: The parsed :class:`TelegramCommand`, or ``None`` if unauthorized or unrecognized.
    """
    if chat_id not in allowed_chat_ids or user_id not in allowed_user_ids:
        return None
    normalized = text.strip().lower()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    if normalized not in {kind.value for kind in TelegramCommandKind}:
        return None
    return TelegramCommand(chat_id=chat_id, user_id=user_id, kind=TelegramCommandKind(normalized))
