import pytest
from fastapi.testclient import TestClient
from psycopg.errors import InsufficientPrivilege
from pydantic import SecretStr

from apps.api.main import create_app
from wallybot.infrastructure.loop import selector_loop

pytestmark = pytest.mark.integration


def test_research_cannot_read_identity_or_spoof_worker(db):
    db.execute("SET ROLE wally_research")
    try:
        with pytest.raises(InsufficientPrivilege):
            db.execute("SELECT * FROM users")
        with pytest.raises(InsufficientPrivilege):
            db.execute("UPDATE control SET status='PAUSED'")
        with pytest.raises(InsufficientPrivilege):
            db.execute("INSERT INTO heartbeats VALUES ('worker', 0)")
        db.execute("INSERT INTO heartbeats VALUES ('research', 0)")
    finally:
        db.execute("RESET ROLE")


def test_runtime_cannot_erase_audit(db):
    db.execute("SET ROLE wally_api")
    try:
        with pytest.raises(InsufficientPrivilege):
            db.execute("DELETE FROM events")
    finally:
        db.execute("RESET ROLE")


def test_redis_outage_blocks_auth_but_not_liveness(settings, db):
    unavailable = settings.model_copy(update={"redis_url": SecretStr("redis://127.0.0.1:1/0")})
    with TestClient(
        create_app(unavailable),
        base_url=settings.origin,
        headers={"Origin": settings.origin},
        backend_options={"loop_factory": selector_loop},
    ) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
        assert (
            client.post(
                "/api/auth/login", json={"username": "admin", "password": "test"}
            ).status_code
            == 503
        )


def test_database_outage_reports_not_ready(settings):
    from sqlalchemy.engine import make_url

    url = make_url(settings.database_url.get_secret_value()).set(port=1)
    unavailable = settings.model_copy(
        update={"database_url": SecretStr(url.render_as_string(hide_password=False))}
    )
    with TestClient(
        create_app(unavailable),
        base_url=settings.origin,
        backend_options={"loop_factory": selector_loop},
    ) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503
