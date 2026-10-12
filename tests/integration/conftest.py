import os
import subprocess
import sys
from pathlib import Path

import psycopg
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from apps.api.main import create_app
from wallybot.infrastructure.loop import selector_loop
from wallybot.infrastructure.settings import Settings
from wallybot.security.crypto import token


@pytest.fixture(scope="session")
def dependencies():
    # Errors intentionally fail, rather than silently skip, when Docker is unavailable.
    with PostgresContainer("postgres:17.11-alpine", driver="psycopg") as pg:
        with RedisContainer("redis:7.4.11-alpine") as redis:
            yield (
                pg.get_connection_url(),
                f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0",
            )


@pytest.fixture(scope="session")
def settings(dependencies):
    db_url, redis_url = dependencies
    api_password = token()
    with psycopg.connect(db_url.replace("+psycopg", ""), autocommit=True) as connection:
        for role in ("api", "worker", "scheduler", "research", "ai"):
            connection.execute(
                psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    psycopg.sql.Identifier("wally_" + role), psycopg.sql.Literal(api_password)
                )
            )
    result = Settings(
        database_url=SecretStr(db_url),
        redis_url=SecretStr(redis_url),
        encryption_key=SecretStr(Fernet.generate_key().decode()),
        bootstrap_token=SecretStr(token()),
        environment="test",
        auth_limit=1000,
        _env_file=None,
    )
    env = os.environ.copy()
    for key, value in result.model_dump().items():
        env["WALLY_" + key.upper()] = (
            value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        cwd=Path(__file__).resolve().parents[2],
        check=True,
    )
    from sqlalchemy.engine import make_url

    api_url = make_url(db_url).set(username="wally_api", password=api_password)
    return result.model_copy(
        update={"database_url": SecretStr(api_url.render_as_string(hide_password=False))}
    )


@pytest.fixture
def db(settings, dependencies):
    with psycopg.connect(dependencies[0].replace("+psycopg", ""), autocommit=True) as connection:
        connection.execute(
            "TRUNCATE sessions, recovery_codes, auth_challenges, users, "
            "events, jobs, heartbeats CASCADE"
        )
        connection.execute("UPDATE control SET setup_complete=false, status='RUNNING'")
        yield connection


@pytest.fixture
def client(settings, db):
    with TestClient(
        create_app(settings),
        base_url=settings.origin,
        headers={"Origin": settings.origin},
        backend_options={"loop_factory": selector_loop},
    ) as client:
        client.app.state.portfolio_market_provider = None
        yield client
