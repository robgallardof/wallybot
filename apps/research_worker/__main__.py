import asyncio

from wallybot.infrastructure.loop import selector_loop
from wallybot.infrastructure.process import run

with asyncio.Runner(loop_factory=selector_loop) as runner:
    runner.run(run("research"))
