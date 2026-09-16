import pytest
from hypothesis import given
from hypothesis import strategies as st

from wallybot.domain.control import Control, Role, Status
from wallybot.security.crypto import digest


@given(st.lists(st.sampled_from(list(Status)), max_size=100))
def test_control_sequence_never_enters_live(changes):
    control = Control()
    for status in changes:
        control = control.change(status, Role.ADMIN)
        assert control.environment == "OBSERVE"


@given(st.sampled_from(list(Status)))
def test_viewer_cannot_mutate(status):
    with pytest.raises(PermissionError):
        Control().change(status, Role.VIEWER)


@given(st.text())
def test_token_digest_fixed_length(value):
    assert len(digest(value)) == 64
