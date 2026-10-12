"""Serialize signed requests across API processes with a persisted nonce per key fingerprint."""

import hashlib
import time
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from wallybot.exchanges.kraken_private import SignedKrakenTransport


class DatabaseKrakenTransport:
    def __init__(
        self, engine: AsyncEngine, key: str, secret: str, client: httpx.AsyncClient
    ) -> None:
        self.engine = engine
        self._key = key
        self._secret = secret
        self._client = client
        self.fingerprint = hashlib.sha256(key.encode()).hexdigest()

    async def call(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        # Session-level lock survives the nonce commit. No financial transaction crosses HTTP.
        async with self.engine.connect() as connection:
            lock_id = int(self.fingerprint[:15], 16)
            try:
                await connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
                nonce = await connection.scalar(
                    text("""
                    INSERT INTO kraken_nonces(key_fingerprint, last_nonce) VALUES (:key, :candidate)
                    ON CONFLICT (key_fingerprint) DO UPDATE
                    SET last_nonce = GREATEST(kraken_nonces.last_nonce + 1, EXCLUDED.last_nonce)
                    RETURNING last_nonce
                """),
                    {"key": self.fingerprint, "candidate": time.time_ns() // 1000},
                )
                await connection.commit()

                async def next_nonce() -> str:
                    return str(nonce)

                transport = SignedKrakenTransport(self._key, self._secret, next_nonce, self._client)
                result = await transport.call(method, params)
                await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                await connection.commit()
                return result
            except BaseException:
                # A cancelled request must never return a session lock to the connection pool.
                await connection.invalidate()
                raise
