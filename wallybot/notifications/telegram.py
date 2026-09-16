"""Narrow outbound Telegram notification adapter.

The bot token is injected by the composition root and is never logged or persisted here.  This
adapter can send a bounded text notification only to configured chats; it cannot place orders,
perform withdrawals, or interpret a chat message as an operation.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class NotificationSeverity(StrEnum):
    """How urgently a :class:`Notification` should be treated by its reader.

    :cvar INFO: Routine status, no action implied.
    :cvar WARNING: Worth attention, not necessarily urgent.
    :cvar CRITICAL: Requires prompt attention.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Notification:
    """A single outbound notification, independent of transport.

    :ivar severity: See :class:`NotificationSeverity`.
    :ivar title: Non-empty short summary.
    :ivar body: Non-empty full message.
    :raises ValueError: If ``title`` or ``body`` is empty.
    """

    severity: NotificationSeverity
    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.title or not self.body:
            raise ValueError("notification title and body are required")

    @property
    def text(self) -> str:
        """Render as the single plain-text string :class:`TelegramNotifier` sends."""
        return f"[{self.severity}] {self.title}\n{self.body}"


class TelegramTransport(Protocol):
    async def post_form(self, url: str, form: dict[str, str]) -> None:
        """Submit ``form`` as a form-encoded POST to ``url``.

        :param url: Full destination URL.
        :param form: Form fields to submit.
        """
        ...


class TelegramNotifier:
    """One-way sender with allowlisted destination chats and no command/execution surface."""

    def __init__(
        self, token: str, allowed_chat_ids: frozenset[int], transport: TelegramTransport
    ) -> None:
        """
        :param token: Telegram bot token; injected by the composition root, never logged.
        :param allowed_chat_ids: Chats this notifier may send to; must be non-empty.
        :param transport: HTTP transport to send through; see :class:`TelegramTransport`.
        :raises ValueError: If ``token`` is empty or ``allowed_chat_ids`` is empty.
        """
        if not token:
            raise ValueError("Telegram token is required")
        if not allowed_chat_ids:
            raise ValueError("at least one Telegram chat must be allowlisted")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._allowed_chat_ids = allowed_chat_ids
        self._transport = transport

    async def notify(self, chat_id: int, notification: Notification) -> None:
        """Send ``notification`` to ``chat_id``.

        :param chat_id: Destination chat; must be on the allowlist passed to the constructor.
        :param notification: The message to send; see :class:`Notification`.
        :raises PermissionError: If ``chat_id`` is not allowlisted.
        :raises ValueError: If the rendered text exceeds Telegram's 4096-character limit.
        """
        if chat_id not in self._allowed_chat_ids:
            raise PermissionError("Telegram chat is not allowlisted")
        text = notification.text
        if len(text) > 4096:
            raise ValueError("Telegram notification exceeds the 4096-character limit")
        await self._transport.post_form(
            self._url,
            {
                "chat_id": str(chat_id),
                "text": text,
                "disable_web_page_preview": "true",
            },
        )
