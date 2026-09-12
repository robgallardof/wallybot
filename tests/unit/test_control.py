import pytest

from wallybot.domain.control import Control, Role, Status


def test_paper_is_only_environment():
    assert Control().environment == "PAPER"
    with pytest.raises(ValueError):
        Control("LIVE")


def test_viewer_cannot_change_controls():
    with pytest.raises(PermissionError):
        Control().change(Status.PAUSED, Role.VIEWER)


def test_pause_keeps_environment():
    state = Control().change(Status.PAUSED, Role.ADMIN)
    assert state.status == Status.PAUSED
    assert state.environment == "PAPER"
