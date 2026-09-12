import asyncio

import pytest
from pydantic import SecretStr

from wallybot.infrastructure.database import database
from wallybot.infrastructure.jobs import tick
from wallybot.infrastructure.loop import selector_loop
from wallybot.infrastructure.settings import ProcessSettings

pytestmark = pytest.mark.integration


def test_scheduler_deduplicates_and_workers_apply_once(db, dependencies):
    async def exercise():
        engine, sessions = database(ProcessSettings(database_url=SecretStr(dependencies[0])))
        try:
            await asyncio.gather(tick("scheduler", sessions, 120), tick("scheduler", sessions, 120))
            await asyncio.gather(tick("worker", sessions, 120), tick("worker", sessions, 120))
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=selector_loop) as runner:
        runner.run(exercise())
    assert db.execute("SELECT status, attempts FROM jobs").fetchall() == [("DONE", 1)]


def test_worker_does_not_claim_unknown_or_future_work(db, dependencies):
    db.execute(
        "INSERT INTO jobs VALUES ('unknown', 'OTHER', 0, 'PENDING', 0), "
        "('future', 'CLEANUP', 9999, 'PENDING', 0)"
    )

    async def exercise():
        engine, sessions = database(ProcessSettings(database_url=SecretStr(dependencies[0])))
        try:
            await tick("worker", sessions, 100)
        finally:
            await engine.dispose()

    with asyncio.Runner(loop_factory=selector_loop) as runner:
        runner.run(exercise())
    assert db.execute("SELECT DISTINCT status, attempts FROM jobs").fetchall() == [("PENDING", 0)]
