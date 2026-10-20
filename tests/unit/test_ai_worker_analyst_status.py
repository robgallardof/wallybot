"""The native worker reports per-CLI availability without touching analyst settings."""

import logging
from contextlib import asynccontextmanager

from apps.ai_worker import worker


class _Analyst:
    def __init__(self, cli: str, last_call_ok: bool | None, ready: bool = True) -> None:
        self.cli = cli
        self.last_call_ok = last_call_ok
        self.ready = ready
        self.readiness_checks = 0

    async def check_ready(self) -> bool:
        self.readiness_checks += 1
        return self.ready


class _Sessions:
    def __init__(self) -> None:
        self.recorded: list[dict] = []

    @asynccontextmanager
    async def begin(self):
        recorded = self.recorded

        class _Db:
            async def execute(self, statement, params):
                assert "record_ai_analyst_status" in str(statement)
                recorded.append(params)

        yield _Db()


async def test_observed_calls_are_recorded_without_extra_readiness_calls() -> None:
    sessions = _Sessions()
    codex, claude = _Analyst("codex", True), _Analyst("claude", False)

    await worker._report_analyst_status(
        sessions, [codex, claude], {}, logging.LoggerAdapter(logging.getLogger("t"))
    )

    assert [(p["analyst"], p["available"]) for p in sessions.recorded] == [
        ("codex", True),
        ("claude", False),
    ]
    assert codex.readiness_checks == claude.readiness_checks == 0


async def test_idle_tick_rechecks_only_when_status_is_missing_or_stale() -> None:
    sessions = _Sessions()
    recorded_at: dict[str, int] = {}
    claude = _Analyst("claude", None, ready=False)
    logger = logging.LoggerAdapter(logging.getLogger("t"))

    await worker._report_analyst_status(sessions, [claude], recorded_at, logger)
    await worker._report_analyst_status(sessions, [claude], recorded_at, logger)

    assert claude.readiness_checks == 1
    assert [(p["analyst"], p["available"]) for p in sessions.recorded] == [("claude", False)]


def test_configured_analysts_follow_the_saved_toggles() -> None:
    from types import SimpleNamespace

    from wallybot.infrastructure.system_clock import SystemClock
    from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator

    settings = SimpleNamespace(
        ai_prompt_version="v", codex_model_id="c", claude_model_id="k", ai_timeout_seconds=5
    )

    def build(codex: bool, claude: bool) -> list[str]:
        control = SimpleNamespace(codex_enabled=codex, claude_enabled=claude)
        analysts = worker._configured_analysts(control, settings, UuidIdGenerator(), SystemClock())
        return [analyst.cli for analyst in analysts]

    assert build(True, True) == ["codex", "claude"]
    assert build(False, True) == ["claude"]
    assert build(False, False) == []
