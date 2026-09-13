"""Disposable browser-test stack; never uses development DB or credentials."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from cryptography.fernet import Fernet
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with PostgresContainer("postgres:17.11-alpine", driver="psycopg") as pg:
        with RedisContainer("redis:7.4.11-alpine") as redis:
            env = os.environ.copy()
            env.update(
                WALLY_DATABASE_URL=pg.get_connection_url(),
                WALLY_REDIS_URL=f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
                WALLY_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                WALLY_BOOTSTRAP_TOKEN="browser-test-only-bootstrap-token-0001",
                WALLY_ENVIRONMENT="test",
                WALLY_ORIGIN="http://localhost:3334",
                WALLY_COOKIE_SECURE="false",
                WALLY_AUTH_LIMIT="1000",
                WALLY_DEV_API="http://127.0.0.1:8001",
            )
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True
            )
            node = shutil.which("node")
            if not node:
                raise SystemExit("Node.js required")
            next_cli = ROOT / "apps/web/node_modules/next/dist/bin/next"
            web_env = {
                key: value
                for key, value in os.environ.items()
                if not key.upper().startswith("WALLY_")
            }
            web_env["WALLY_DEV_API"] = "http://127.0.0.1:8001"
            web_env["NEXT_TELEMETRY_DISABLED"] = "1"
            production = os.environ.get("WALLY_E2E_PRODUCTION") == "1"
            if production:
                subprocess.run(
                    [node, str(next_cli), "build"], cwd=ROOT / "apps/web", env=web_env, check=True
                )
            children = []
            try:
                children.append(
                    subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "apps.api.main:create_app",
                            "--factory",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            "8001",
                            "--loop",
                            "wallybot.infrastructure.loop:selector_loop",
                            "--no-access-log",
                            "--no-proxy-headers",
                        ],
                        cwd=ROOT,
                        env=env,
                    )
                )
                children.append(
                    subprocess.Popen(
                        [
                            node,
                            str(next_cli),
                            "start" if production else "dev",
                            "--hostname",
                            "127.0.0.1",
                            "--port",
                            "3334",
                        ],
                        cwd=ROOT / "apps/web",
                        env=web_env,
                    )
                )
                while all(child.poll() is None for child in children):
                    time.sleep(0.5)
            finally:
                for child in children:
                    if child.poll() is None:
                        child.terminate()
                for child in children:
                    child.wait(timeout=10)


if __name__ == "__main__":
    main()
