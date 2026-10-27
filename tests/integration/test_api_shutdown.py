"""API shutdown must finish while its real database metrics task is starting."""

import json
import subprocess
import sys
from pathlib import Path

from pydantic import SecretStr


def test_repeated_api_shutdown_during_metrics_startup(settings):
    """Bound the real child so a background-task cancellation regression fails, not hangs."""
    config = {
        key: value.get_secret_value() if isinstance(value, SecretStr) else value
        for key, value in settings.model_dump(mode="python").items()
    }
    child = """
import json
import sys
from fastapi.testclient import TestClient
from apps.api.main import create_app
from wallybot.infrastructure.loop import selector_loop
from wallybot.infrastructure.settings import Settings

config = Settings(**json.load(sys.stdin), _env_file=None)
for _ in range(20):
    with TestClient(create_app(config), backend_options={"loop_factory": selector_loop}):
        pass
"""
    result = subprocess.run(
        [sys.executable, "-c", child],
        input=json.dumps(config, default=str),
        text=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=45,
        check=False,
    )
    # Do not include subprocess streams: the child receives disposable test credentials.
    assert result.returncode == 0, "Repeated API startup/shutdown failed"
