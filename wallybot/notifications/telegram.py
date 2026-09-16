"""Narrow outbound Telegram notification adapter.

The bot token is injected by the composition root and is never logged or persisted here.  This
adapter can send a bounded text notification only to configured chats; it cannot place orders,
perform withdrawals, or interpret a chat message as an operation.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class NotificationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Notification:
    severity: NotificationSeverity
    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.title or not self.body:
            raise ValueError("notification title and body are required")

    @property
    def text(self) -> str:
        return f"[{self.severity}] {self.title}\n{self.body}"


class TelegramTransport(Protocol):
    async def post_form(self, url: str, form: dict[str, str]) -> None: ...


class TelegramNotifier:
    """One-way sender with allowlisted destination chats and no command/execution surface."""

    def __init__(
        self, token: str, allowed_chat_ids: frozenset[int], transport: TelegramTransport
    ) -> None:
        if not token:
            raise ValueError("Telegram token is required")
        if not allowed_chat_ids:
            raise ValueError("at least one Telegram chat must be allowlisted")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._allowed_chat_ids = allowed_chat_ids
        self._transport = transport

    async def notify(self, chat_id: int, notification: Notification) -> None:
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
