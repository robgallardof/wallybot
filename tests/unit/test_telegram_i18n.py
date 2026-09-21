import pytest

from wallybot.notifications.telegram_i18n import resolve_language


@pytest.mark.parametrize(
    "code,expected",
    [
        ("en", "en"),
        ("en-US", "en"),
        ("EN", "en"),
        ("es", "es"),
        ("es-AR", "es"),
        ("pt-BR", "es"),
        (None, "es"),
        ("", "es"),
    ],
)
def test_resolve_language(code: str | None, expected: str):
    assert resolve_language(code) == expected
