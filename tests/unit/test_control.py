import pytest

from wallybot.domain.control import Control, Role, Status


def test_observe_is_default_and_paper_is_opt_in():
    assert Control().environment == "OBSERVE"
    assert Control("PAPER").environment == "PAPER"
    assert Control("LIVE").environment == "LIVE"
    with pytest.raises(ValueError):
        Control("UNKNOWN")


def test_viewer_cannot_change_controls():
    with pytest.raises(PermissionError):
        Control().change(Status.PAUSED, Role.VIEWER)


def test_pause_keeps_environment():
    state = Control().change(Status.PAUSED, Role.ADMIN)
    assert state.status == Status.PAUSED
    assert state.environment == "OBSERVE"
