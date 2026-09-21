"""EN/ES text for Telegram bot replies.

Keyed by Telegram's own `message.from.language_code` -- there is no stored per-chat language
preference anywhere in this codebase, and the sender's own Telegram client language is the
natural, already-available signal to reply in. Not a general i18n framework (no ICU plurals, no
`.po` files): this bot has a small, fixed set of replies, so a two-language dict is the simplest
thing that actually works, matching this codebase's own "avoid speculative architecture" rule.
"""

from typing import Literal

Language = Literal["es", "en"]


def resolve_language(telegram_language_code: str | None) -> Language:
    """Telegram's `language_code` is a BCP 47 tag (e.g. "en", "en-US", "es-AR") -- only the
    primary subtag matters here. Anything not English falls back to Spanish, this bot's original
    and still-primary language, rather than silently defaulting to English for an unrecognized
    code."""
    return "en" if (telegram_language_code or "").lower().startswith("en") else "es"
