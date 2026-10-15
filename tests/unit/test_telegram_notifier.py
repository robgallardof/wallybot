import json

import pytest

from wallybot.notifications.telegram import (
    Notification,
    NotificationSeverity,
    TelegramNotifier,
)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post_form(self, url: str, form: dict[str, str]) -> None:
        self.calls.append((url, form))


async def test_sends_bounded_message_only_to_an_allowlisted_chat() -> None:
    transport = FakeTransport()
    notifier = TelegramNotifier("secret-token", frozenset({123}), transport)

    await notifier.notify(123, Notification(NotificationSeverity.WARNING, "Data stale", "Paused."))

    assert transport.calls == [
        (
            "https://api.telegram.org/botsecret-token/sendMessage",
            {
                "chat_id": "123",
                "text": "[WARNING] Data stale\nPaused.",
                "disable_web_page_preview": "true",
            },
        )
    ]


async def test_rejects_an_unallowlisted_chat_without_sending() -> None:
    transport = FakeTransport()
    notifier = TelegramNotifier("secret-token", frozenset({123}), transport)

    with pytest.raises(PermissionError, match="allowlisted"):
        await notifier.notify(999, Notification(NotificationSeverity.INFO, "Status", "Ready."))

    assert transport.calls == []


async def test_rejects_message_that_telegram_would_truncate() -> None:
    transport = FakeTransport()
    notifier = TelegramNotifier("secret-token", frozenset({123}), transport)

    with pytest.raises(ValueError, match="4096"):
        await notifier.notify(123, Notification(NotificationSeverity.INFO, "Status", "x" * 4096))

    assert transport.calls == []


async def test_inline_buttons_reach_the_telegram_transport():
    transport = FakeTransport()
    notifier = TelegramNotifier("synthetic", frozenset({42}), transport)
    markup = {
        "inline_keyboard": [
            [{"text": "Aprobar · LIVE", "callback_data": "approve:proposal:LIVE:3"}]
        ]
    }
    await notifier.notify(42, Notification(NotificationSeverity.INFO, "Proposal", "Why", markup))
    assert json.loads(transport.calls[0][1]["reply_markup"]) == markup
