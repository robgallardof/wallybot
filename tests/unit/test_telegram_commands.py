import pytest

from wallybot.application.telegram_commands import TelegramCommand, parse_command


@pytest.mark.parametrize(
    "text,expected",
    [
        ("/status", TelegramCommand.STATUS),
        ("/breakers", TelegramCommand.BREAKERS),
        ("/portfolio", TelegramCommand.PORTFOLIO),
        ("/proposals", TelegramCommand.PROPOSALS),
        ("/approve proposal-1", TelegramCommand.APPROVE),
        ("/reject@wallybot_bot proposal-1", TelegramCommand.REJECT),
        ("/simulate proposal-1", TelegramCommand.SIMULATE),
        ("/withdrawal", TelegramCommand.WITHDRAWAL),
        ("/pause", TelegramCommand.PAUSE),
        ("/resume", TelegramCommand.RESUME),
        ("/STATUS", TelegramCommand.STATUS),
        ("  /status  ", TelegramCommand.STATUS),
        ("/status@wallybot_bot", TelegramCommand.STATUS),
        ("/pause now please", TelegramCommand.PAUSE),
        ("/help", TelegramCommand.HELP),
        ("/commands", TelegramCommand.HELP),
        ("/start", TelegramCommand.HELP),
        ("/HELP", TelegramCommand.HELP),
    ],
)
def test_recognized_commands_parse(text: str, expected: TelegramCommand):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "hello", "/unknown", "status", "pause"])
def test_unrecognized_text_parses_to_none(text: str):
    assert parse_command(text) is None
