import asyncio
import signal
import tempfile
import time
from pathlib import Path

from redis.asyncio import Redis

from wallybot.infrastructure.database import database
from wallybot.infrastructure.jobs import tick
from wallybot.infrastructure.logging import configure_logging
from wallybot.infrastructure.settings import load_process_settings


def write_heartbeat(service: str, now: int) -> None:
    folder = Path(tempfile.gettempdir())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"wally-{service}.heartbeat").write_text(str(now))


async def run(service: str) -> None:
    settings = load_process_settings()
    engine, sessions = database(settings)
    logger = configure_logging(service)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            pass  # Windows launcher terminates its tracked child processes.
    redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=3)
    try:
        while not stopping.is_set():
            try:
                now = int(time.time())
                await tick(service, sessions, now)
                await asyncio.to_thread(write_heartbeat, service, now)
                if service == "scheduler":
                    try:
                        await redis.publish("jobs:wakeup", "scan")
                    except Exception:
                        logger.warning("WAKEUP_UNAVAILABLE_DB_POLL_RETAINS_WORK")
            except Exception:
                logger.warning("DEPENDENCY_UNAVAILABLE")
            try:
                await asyncio.wait_for(stopping.wait(), timeout=5)
            except TimeoutError:
                pass
    finally:
        await redis.aclose()
        await engine.dispose()
