"""Pure parsing of an inbound Telegram message's text into a recognized command.

Deliberately narrow: any text that isn't exactly one of the known commands (optionally with a
Telegram group-style `@BotName` suffix, or trailing arguments -- ignored, none of these commands
take one) parses to `None` and is silently ignored by the caller. There is no free-text chat
surface here, only a fixed command set.
"""

from enum import StrEnum


class TelegramCommand(StrEnum):
    STATUS = "STATUS"
    BREAKERS = "BREAKERS"
    PORTFOLIO = "PORTFOLIO"
    PROPOSALS = "PROPOSALS"
    WITHDRAWAL = "WITHDRAWAL"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    HELP = "HELP"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SIMULATE = "SIMULATE"
    INIT = "INIT"


_COMMANDS: dict[str, TelegramCommand] = {
    "/status": TelegramCommand.STATUS,
    "/breakers": TelegramCommand.BREAKERS,
    "/portfolio": TelegramCommand.PORTFOLIO,
    "/proposals": TelegramCommand.PROPOSALS,
    "/proposal": TelegramCommand.PROPOSALS,
    "/withdrawal": TelegramCommand.WITHDRAWAL,
    "/pause": TelegramCommand.PAUSE,
    "/resume": TelegramCommand.RESUME,
    "/help": TelegramCommand.HELP,
    "/commands": TelegramCommand.HELP,
    "/start": TelegramCommand.HELP,
    "/approve": TelegramCommand.APPROVE,
    "/reject": TelegramCommand.REJECT,
    "/simulate": TelegramCommand.SIMULATE,
    "/init": TelegramCommand.INIT,
}


def parse_command(text: str) -> TelegramCommand | None:
    stripped = text.strip()
    if not stripped:
        return None
    first_token = stripped.split()[0].lower()
    # Strip a Telegram group-style "@BotName" suffix (e.g. "/status@wallybot_bot").
    first_token = first_token.split("@")[0]
    return _COMMANDS.get(first_token)
