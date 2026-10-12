"""Explicit local CLI readiness check; no DB, market access or proposal persistence."""

import asyncio

from wallybot.infrastructure.system_clock import SystemClock
from wallybot.infrastructure.uuid_id_generator import UuidIdGenerator
from wallybot.intelligence.cli_ai_provider import CliAiProvider


async def main() -> None:
    providers = [
        CliAiProvider(
            cli=name,
            model_id=name,
            prompt_version="readiness/v1",
            id_generator=UuidIdGenerator(),
            clock=SystemClock(),
        )
        for name in ("codex", "claude")
    ]
    results = await asyncio.gather(*(provider.check_ready() for provider in providers))
    for name, ready in zip(("Codex", "Claude"), results, strict=True):
        print(f"{name}: {'READY' if ready else 'UNAVAILABLE'}")
    if not all(results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
