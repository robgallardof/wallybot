from redis.asyncio import Redis

from wallybot.security.crypto import digest

SCRIPT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


class Throttled(Exception):
    pass


class Throttle:
    def __init__(self, redis: Redis, limit: int, seconds: int) -> None:
        self.redis = redis
        self.limit = limit
        self.seconds = seconds

    async def check(self, scope: str) -> None:
        count = await self.redis.execute_command(
            "EVAL", SCRIPT, 1, "auth:" + digest(scope), self.seconds
        )
        if int(count) > self.limit:  # type: ignore[arg-type]
            raise Throttled
