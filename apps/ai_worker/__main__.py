import asyncio

from apps.ai_worker.worker import run_ai_worker
from wallybot.infrastructure.loop import selector_loop

with asyncio.Runner(loop_factory=selector_loop) as runner:
    runner.run(run_ai_worker())
