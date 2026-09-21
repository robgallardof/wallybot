from datetime import UTC, datetime, timedelta

import pytest

from wallybot.domain.telegram_confirmation import (
    CONFIRMATION_TTL,
    TelegramAction,
    TelegramConfirmation,
)

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def test_confirmation_ttl_is_five_minutes():
    assert CONFIRMATION_TTL == timedelta(minutes=5)


def test_expires_at_must_be_after_requested_at():
    with pytest.raises(ValueError):
        TelegramConfirmation(
            confirmation_id="c1",
            action=TelegramAction.PAUSE,
            requested_at=AS_OF,
            expires_at=AS_OF,
        )


def test_confirmed_at_cannot_precede_requested_at():
    with pytest.raises(ValueError):
        TelegramConfirmation(
            confirmation_id="c1",
            action=TelegramAction.PAUSE,
            requested_at=AS_OF,
            expires_at=AS_OF + CONFIRMATION_TTL,
            confirmed_at=AS_OF - timedelta(seconds=1),
        )


def test_a_fresh_confirmation_is_pending_and_not_confirmed():
    confirmation = TelegramConfirmation(
        confirmation_id="c1",
        action=TelegramAction.PAUSE,
        requested_at=AS_OF,
        expires_at=AS_OF + CONFIRMATION_TTL,
    )
    assert confirmation.is_pending is True
    assert confirmation.is_confirmed is False
    assert confirmation.is_expired(AS_OF) is False
    assert confirmation.is_expired(AS_OF + CONFIRMATION_TTL) is True


def test_a_confirmed_confirmation_is_no_longer_pending():
    confirmation = TelegramConfirmation(
        confirmation_id="c1",
        action=TelegramAction.RESUME,
        requested_at=AS_OF,
        expires_at=AS_OF + CONFIRMATION_TTL,
        confirmed_at=AS_OF + timedelta(minutes=1),
        confirmed_by="admin-1",
    )
    assert confirmation.is_confirmed is True
    assert confirmation.is_pending is False
