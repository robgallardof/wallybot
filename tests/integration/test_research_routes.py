import pyotp
import pytest

pytestmark = pytest.mark.integration


def enroll(client, settings) -> None:
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    started = client.post("/api/auth/setup/start", json=body)
    assert started.status_code == 200, started.text
    enrollment = started.json()
    finished = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finished.status_code == 200, finished.text


def create_job(client, csrf, experiment_id: str = "exp-1", purpose: str = "backtest re-run"):
    return client.post(
        "/api/research/jobs",
        json={"experiment_id": experiment_id, "purpose": purpose},
        headers={"X-CSRF-Token": csrf},
    )


def test_research_job_routes_require_auth(client) -> None:
    assert client.get("/api/research/jobs").status_code == 401
    assert client.post("/api/research/jobs", json={}).status_code == 401
    assert client.request("DELETE", "/api/research/jobs/job-1", json={}).status_code == 401


def test_viewer_can_list_but_not_create_or_cancel(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role = 'VIEWER'")

    assert client.get("/api/research/jobs").status_code == 200
    assert create_job(client, csrf).status_code == 403
    assert (
        client.request(
            "DELETE", "/api/research/jobs/job-1", json={}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 403
    )


def test_admin_creates_a_pending_job_and_it_appears_in_the_list(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = create_job(client, csrf, experiment_id="exp-42", purpose="check drift")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["experiment_id"] == "exp-42"
    assert body["purpose"] == "check drift"
    assert body["status"] == "PENDING"
    assert body["attempts"] == 0
    assert body["cancel_requested"] is False
    assert body["artifact_uri"] is None
    assert body["error"] is None

    rows = client.get("/api/research/jobs").json()["rows"]
    assert len(rows) == 1
    assert rows[0]["id"] == body["id"]


def test_cancelling_a_pending_job_marks_it_cancelled(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    job_id = create_job(client, csrf).json()["id"]

    response = client.request(
        "DELETE", f"/api/research/jobs/{job_id}", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"


def test_cancelling_an_unknown_job_is_a_404(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    response = client.request(
        "DELETE", "/api/research/jobs/does-not-exist", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 404


def test_cancelling_an_already_cancelled_job_is_rejected(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    job_id = create_job(client, csrf).json()["id"]
    client.request(
        "DELETE", f"/api/research/jobs/{job_id}", json={}, headers={"X-CSRF-Token": csrf}
    )

    response = client.request(
        "DELETE", f"/api/research/jobs/{job_id}", json={}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 404


def test_the_queue_depth_quota_rejects_a_sixth_active_job(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    for i in range(5):
        assert create_job(client, csrf, experiment_id=f"exp-{i}").status_code == 200

    response = create_job(client, csrf, experiment_id="exp-one-too-many")

    assert response.status_code == 429
    rows = client.get("/api/research/jobs").json()["rows"]
    assert len(rows) == 5


def test_cancelling_one_job_frees_a_quota_slot(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    job_ids = [create_job(client, csrf, experiment_id=f"exp-{i}").json()["id"] for i in range(5)]
    client.request(
        "DELETE", f"/api/research/jobs/{job_ids[0]}", json={}, headers={"X-CSRF-Token": csrf}
    )

    response = create_job(client, csrf, experiment_id="exp-fits-now")

    assert response.status_code == 200, response.text
