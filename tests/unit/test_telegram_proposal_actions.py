from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from apps.api.proposal_routes import decide_from_telegram
from tests.unit.test_proposal_presentation import NOW
from wallybot.application.telegram_command_loop import (
    _handle_callback,
    _handle_command,
    _private_operator,
    run_telegram_command_tick,
)
from wallybot.infrastructure.live_models import LiveControlRow
from wallybot.infrastructure.models import ControlRow, UserRow


def callback(**overrides):
    fields = dict(
        id="click-1",
        data="approve:proposal-1:LIVE:3",
        message={"chat": {"id": 42, "type": "private"}, "message_id": 5},
        **{"from": {"id": 42, "language_code": "es"}},
    )
    fields.update(overrides)
    return fields


async def test_button_acknowledges_and_decides_without_mfa():
    decide = AsyncMock(
        return_value={
            "status": "APPROVED",
            "execution_status": "BLOCKED",
            "execution_reason": "Insufficient cash",
        }
    )
    transport = SimpleNamespace(post_form=AsyncMock())
    await _handle_callback(callback(), 42, decide, transport, "https://synthetic.invalid")
    decide.assert_awaited_once_with("proposal-1", "approve", "LIVE:3")
    calls = transport.post_form.await_args_list
    assert calls[0].args[0].endswith("/answerCallbackQuery")
    assert "Propuesta aprobada" in calls[1].args[1]["text"]
    assert "Insufficient cash" in calls[1].args[1]["text"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"from": {"id": 99}},
        {"from": {"id": 42, "is_bot": True}},
        {"message": {"chat": {"id": -42, "type": "group"}}},
        {"message": {"chat": {"id": 42, "type": "group"}}},
        {"message": None},
        {"data": "approve:proposal-1"},
        {"data": "approve:proposal-1:LIVE:3:extra"},
        {"data": "withdraw:proposal-1:LIVE:3"},
    ],
)
async def test_untrusted_or_malformed_button_never_decides(overrides):
    decide, transport = AsyncMock(), SimpleNamespace(post_form=AsyncMock())
    await _handle_callback(
        callback(**overrides), 42, decide, transport, "https://synthetic.invalid"
    )
    decide.assert_not_awaited()
    assert transport.post_form.await_args.args[0].endswith("/answerCallbackQuery")


async def test_typed_command_decides_without_an_mfa_argument():
    decide = AsyncMock(return_value={"status": "APPROVED", "execution_status": "OBSERVE_ONLY"})
    reply = await _handle_command(
        MagicMock(), None, "owner", MagicMock(), NOW, "/approve proposal-1", "es", decide=decide
    )
    decide.assert_awaited_once_with("proposal-1", "approve", None)
    assert "Propuesta aprobada" in reply


def test_identity_requires_private_chat_and_matching_sender():
    data = callback()
    assert _private_operator({**data["message"], "from": data["from"]}, 42)
    assert not _private_operator({"chat": {"id": 42, "type": "private"}}, 42)


def state_with_user(role="ADMIN", environment="OBSERVE"):
    db = AsyncMock()
    db.get.side_effect = [UserRow(id="owner", role=role), ControlRow(environment=environment), None]
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=db)
    session.__aexit__ = AsyncMock(return_value=None)
    return SimpleNamespace(
        sessions=MagicMock(return_value=session),
        throttle=SimpleNamespace(check=AsyncMock()),
        auth=SimpleNamespace(verify_totp=AsyncMock()),
    )


async def test_api_internal_path_keeps_shared_decision_and_does_not_verify_totp():
    state = state_with_user()
    with patch("apps.api.proposal_routes.record_decision", new=AsyncMock()) as record:
        await decide_from_telegram(state, "owner", "proposal-1", "approve", "OBSERVE:0")
    state.auth.verify_totp.assert_not_awaited()
    assert record.await_args.args[:4] == (state, "owner", "proposal-1", "approve")
    assert record.await_args.args[4].environment == "OBSERVE"


async def test_mode_change_rejects_stale_button_before_recording():
    state = state_with_user(environment="PAPER")
    with patch("apps.api.proposal_routes.record_decision", new=AsyncMock()) as record:
        with pytest.raises(HTTPException, match="Mode or limits changed"):
            await decide_from_telegram(state, "owner", "proposal-1", "approve", "OBSERVE:0")
    record.assert_not_awaited()


async def test_live_limits_change_rejects_stale_button():
    state = state_with_user(environment="LIVE")
    db = state.sessions.return_value.__aenter__.return_value
    db.get.side_effect = [
        UserRow(id="owner", role="ADMIN"),
        ControlRow(environment="LIVE"),
        LiveControlRow(owner_id="owner", version=4),
    ]
    with patch("apps.api.proposal_routes.record_decision", new=AsyncMock()) as record:
        with pytest.raises(HTTPException, match="Mode or limits changed"):
            await decide_from_telegram(state, "owner", "proposal-1", "approve", "LIVE:3")
    record.assert_not_awaited()


async def test_viewer_cannot_decide_from_telegram():
    state = state_with_user(role="VIEWER")
    with patch("apps.api.proposal_routes.record_decision", new=AsyncMock()) as record:
        with pytest.raises(HTTPException, match="Administrator required"):
            await decide_from_telegram(state, "owner", "proposal-1", "approve")
    record.assert_not_awaited()


@pytest.mark.parametrize(
    "kind,authorized",
    [
        ("private", True),
        ("callback", True),
        ("group", False),
        ("missing_sender", False),
        ("foreign", False),
    ],
)
async def test_poll_routes_only_private_operator_decisions(kind, authorized):
    message = {
        "chat": {"id": 42, "type": "group" if kind == "group" else "private"},
        "from": {"id": 42},
        "text": "/approve proposal-1",
    }
    if kind == "missing_sender":
        message.pop("from")
    if kind == "foreign":
        message["chat"]["id"] = 99
    update = {"update_id": 100, "message": message}
    if kind == "callback":
        update = {"update_id": 100, "callback_query": callback()}
    transport = SimpleNamespace(
        get_json=AsyncMock(return_value={"result": [update]}), post_form=AsyncMock()
    )
    db = AsyncMock()
    db.scalar.return_value = None
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=db)
    session.__aexit__ = AsyncMock(return_value=None)
    sessions = MagicMock(return_value=session)
    sessions.begin.return_value = session
    config = SimpleNamespace(
        encrypted_bot_token="synthetic", chat_id=42, enabled=True, last_update_id=99
    )
    repo = SimpleNamespace(get=AsyncMock(return_value=config), set_last_update_id=AsyncMock())
    decide = AsyncMock(return_value={"status": "APPROVED", "execution_status": "OBSERVE_ONLY"})
    with patch(
        "wallybot.application.telegram_command_loop.TelegramConfigRepository", return_value=repo
    ):
        await run_telegram_command_tick(
            sessions,
            SimpleNamespace(decrypt=lambda _: "synthetic"),
            transport,
            MagicMock(),
            None,
            NOW,
            owner_id="owner",
            decide=decide,
        )
    assert decide.await_count == int(authorized)
    repo.set_last_update_id.assert_awaited_once_with(100)
