from wallybot.domain.telegram_command import (
    TelegramCommandKind,
    parse_authorized_telegram_command,
)

ALLOWED_CHATS = frozenset({100})
ALLOWED_USERS = frozenset({200})


def test_allowlisted_read_only_command_is_parsed() -> None:
    command = parse_authorized_telegram_command("/status", 100, 200, ALLOWED_CHATS, ALLOWED_USERS)
    assert command is not None
    assert command.kind is TelegramCommandKind.STATUS


def test_untrusted_or_mutating_input_is_rejected() -> None:
    for text, chat_id, user_id in (
        ("/pause", 100, 200),
        ("/report now", 100, 200),
        ("/status", 101, 200),
        ("/status", 100, 201),
    ):
        assert (
            parse_authorized_telegram_command(
                text, chat_id, user_id, ALLOWED_CHATS, ALLOWED_USERS
            )
            is None
        )
