"""POST/GET /api/ai-autonomy/control -- a toggle deliberately separate from /api/control, reusing
the same Admin (ADMIN role + fresh MFA) dependency.
See docs/adr/016-ai-autonomous-account.md (2026-09-23).
"""

import pyotp
import pytest

pytestmark = pytest.mark.integration


def enroll(client, settings):
    body = {
        "username": "admin",
        "password": "correct-horse-battery-staple",
        "bootstrap_token": settings.bootstrap_token.get_secret_value(),
    }
    result = client.post("/api/auth/setup/start", json=body)
    assert result.status_code == 200, result.text
    enrollment = result.json()
    finish = client.post(
        "/api/auth/setup/finish",
        json={
            "bootstrap_token": body["bootstrap_token"],
            "challenge": enrollment["challenge"],
            "code": pyotp.TOTP(enrollment["secret"]).now(),
        },
    )
    assert finish.status_code == 200, finish.text
    return enrollment, finish.json()


def test_unauthenticated_requests_are_rejected(client) -> None:
    assert client.get("/api/ai-autonomy/control").status_code == 401
    assert client.post("/api/ai-autonomy/control", json={"status": "ENABLED"}).status_code == 401


def test_default_state_is_disabled_seventy_twenty_ten(client, settings) -> None:
    enroll(client, settings)

    result = client.get("/api/ai-autonomy/control")

    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "DISABLED"
    assert body["target_core_pct"] == "0.70"
    assert body["target_growth_pct"] == "0.20"
    assert body["target_speculative_pct"] == "0.10"
    assert body["digest_interval_hours"] == 6
    assert body["codex_enabled"] is True
    assert body["claude_enabled"] is True
    assert body["require_consensus"] is True


def test_admin_can_enable_and_it_is_audited(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    result = client.post(
        "/api/ai-autonomy/control", json={"status": "ENABLED"}, headers={"X-CSRF-Token": csrf}
    )

    assert result.status_code == 200
    assert result.json()["status"] == "ENABLED"
    assert db.execute("SELECT status FROM ai_autonomy_control WHERE id = 1").fetchone()[0] == (
        "ENABLED"
    )
    assert (
        db.execute("SELECT count(*) FROM events WHERE event = 'AI_AUTONOMY_ENABLED'").fetchone()[0]
        == 1
    )


def test_viewer_is_forbidden(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    db.execute("UPDATE users SET role='VIEWER'")

    result = client.post(
        "/api/ai-autonomy/control", json={"status": "ENABLED"}, headers={"X-CSRF-Token": csrf}
    )

    assert result.status_code == 403


def test_tier_targets_not_summing_to_one_is_rejected(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    result = client.post(
        "/api/ai-autonomy/control",
        json={"status": "DISABLED", "target_core_pct": "0.50"},
        headers={"X-CSRF-Token": csrf},
    )

    assert result.status_code == 422


def test_updating_all_three_tier_targets_together_succeeds(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    result = client.post(
        "/api/ai-autonomy/control",
        json={
            "status": "DISABLED",
            "target_core_pct": "0.50",
            "target_growth_pct": "0.30",
            "target_speculative_pct": "0.20",
        },
        headers={"X-CSRF-Token": csrf},
    )

    assert result.status_code == 200
    body = result.json()
    assert body["target_core_pct"] == "0.50"
    assert body["target_growth_pct"] == "0.30"
    assert body["target_speculative_pct"] == "0.20"


def test_admin_can_choose_a_single_analyst_only_when_strict_consensus_is_disabled(
    client, settings
) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    result = client.post(
        "/api/ai-autonomy/control",
        json={
            "status": "DISABLED",
            "codex_enabled": False,
            "claude_enabled": True,
            "require_consensus": False,
        },
        headers={"X-CSRF-Token": csrf},
    )

    assert result.status_code == 200
    assert result.json()["codex_enabled"] is False
    assert result.json()["claude_enabled"] is True
    assert result.json()["require_consensus"] is False


def test_strict_consensus_rejects_disabling_either_analyst(client, settings) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]

    result = client.post(
        "/api/ai-autonomy/control",
        json={"status": "DISABLED", "codex_enabled": False, "require_consensus": True},
        headers={"X-CSRF-Token": csrf},
    )

    assert result.status_code == 422
    assert "strict consensus" in result.json()["detail"]


def test_no_op_change_is_not_audited_again(client, settings, db) -> None:
    enroll(client, settings)
    csrf = client.get("/api/auth/me").json()["csrf"]
    client.post(
        "/api/ai-autonomy/control", json={"status": "DISABLED"}, headers={"X-CSRF-Token": csrf}
    )

    count_before = db.execute("SELECT count(*) FROM events").fetchone()[0]
    result = client.post(
        "/api/ai-autonomy/control", json={"status": "DISABLED"}, headers={"X-CSRF-Token": csrf}
    )

    assert result.status_code == 200
    assert db.execute("SELECT count(*) FROM events").fetchone()[0] == count_before
