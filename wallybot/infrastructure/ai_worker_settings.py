"""Settings for `apps/ai_worker` -- the one process in this codebase that runs natively on the
host instead of in a Docker container, so it can shell out to the user's own already-authenticated
`claude`/`codex` CLI. A dedicated, minimal settings class rather
than extending `wallybot.infrastructure.settings.ProcessSettings` -- this process needs no Redis
(a single independent polling loop has nothing to subscribe a wakeup from) and no historical-data
root, and its CLI-specific fields have no reason to exist on every other process's settings.

Uses an explicit environment/local setting or the dedicated native analyst credential file.
It never runs inside the Docker secrets environment; see docs/runbooks/native-ai-worker.md.
"""

import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class AiWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WALLY_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    codex_model_id: str = "codex"
    claude_model_id: str = "claude"
    ai_prompt_version: str = "v2-es"
    ai_timeout_seconds: float = 120.0
    # Wake often so UI/Telegram requests (/init, availability checks) are picked up quickly;
    # the full market analysis itself runs on the slower cadences below.
    ai_poll_interval_seconds: float = 60.0
    # Analysis runs on 1h candles, so scanning faster only repeats the same evidence: look for
    # entries every 30 min while flat and review open positions every closed hour.
    ai_flat_analysis_interval_seconds: float = 1800.0
    ai_holding_analysis_interval_seconds: float = 3600.0


def load_ai_worker_settings() -> AiWorkerSettings:
    try:
        return AiWorkerSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        if not any(e["loc"] == ("database_url",) and e["type"] == "missing" for e in exc.errors()):
            raise
    # Runtime-only credential consumption, exactly like the container settings loader. Neither
    # the URL nor validation inputs are logged; only the dedicated analyst role is loaded here.
    path = Path(os.environ.get("WALLY_AI_DATABASE_URL_FILE", ".secrets/ai_database_url"))
    if not path.is_file():
        raise RuntimeError("Configure WALLY_DATABASE_URL or WALLY_AI_DATABASE_URL_FILE")
    value = path.read_text(encoding="utf-8").strip()
    parsed = urlsplit(value)
    if parsed.hostname == "postgres":
        port = int(os.environ.get("WALLY_AI_DATABASE_PORT", "5433"))
        if not 1 <= port <= 65535:
            raise ValueError("WALLY_AI_DATABASE_PORT must be between 1 and 65535")
        credentials, separator, _host = parsed.netloc.rpartition("@")
        netloc = f"{credentials}{separator}127.0.0.1:{port}"
        value = urlunsplit(parsed._replace(netloc=netloc))
    return AiWorkerSettings(database_url=SecretStr(value))
