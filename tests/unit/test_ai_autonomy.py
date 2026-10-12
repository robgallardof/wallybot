from decimal import Decimal

import pytest

from wallybot.domain.ai_autonomy import AiAutonomyControl, AiAutonomyStatus
from wallybot.domain.control import Role


def test_defaults_are_disabled_and_seventy_twenty_ten() -> None:
    control = AiAutonomyControl()

    assert control.status == AiAutonomyStatus.DISABLED
    assert control.target_core_pct == Decimal("0.70")
    assert control.target_growth_pct == Decimal("0.20")
    assert control.target_speculative_pct == Decimal("0.10")
    assert control.digest_interval_hours == 6
    assert control.codex_enabled is True
    assert control.claude_enabled is True
    assert control.require_consensus is True


def test_tier_targets_must_sum_to_exactly_one() -> None:
    with pytest.raises(ValueError, match="sum to exactly 1"):
        AiAutonomyControl(
            target_core_pct=Decimal("0.50"),
            target_growth_pct=Decimal("0.20"),
            target_speculative_pct=Decimal("0.10"),
        )


def test_a_negative_tier_target_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_core_pct"):
        AiAutonomyControl(
            target_core_pct=Decimal("-0.10"),
            target_growth_pct=Decimal("0.90"),
            target_speculative_pct=Decimal("0.20"),
        )


def test_non_positive_digest_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match="digest_interval_hours"):
        AiAutonomyControl(digest_interval_hours=0)


def test_change_requires_admin_role() -> None:
    control = AiAutonomyControl()

    with pytest.raises(PermissionError):
        control.change(role=Role.VIEWER, status=AiAutonomyStatus.ENABLED)


def test_change_toggles_status_and_keeps_other_fields() -> None:
    control = AiAutonomyControl()

    changed = control.change(role=Role.ADMIN, status=AiAutonomyStatus.ENABLED)

    assert changed.status == AiAutonomyStatus.ENABLED
    assert changed.target_core_pct == control.target_core_pct
    assert changed.digest_interval_hours == control.digest_interval_hours


def test_change_can_update_all_tier_targets_together() -> None:
    control = AiAutonomyControl()

    changed = control.change(
        role=Role.ADMIN,
        status=AiAutonomyStatus.DISABLED,
        target_core_pct=Decimal("0.50"),
        target_growth_pct=Decimal("0.30"),
        target_speculative_pct=Decimal("0.20"),
    )

    assert changed.target_core_pct == Decimal("0.50")
    assert changed.target_growth_pct == Decimal("0.30")
    assert changed.target_speculative_pct == Decimal("0.20")


def test_change_rejects_a_partial_update_that_breaks_the_sum_invariant() -> None:
    control = AiAutonomyControl()

    with pytest.raises(ValueError, match="sum to exactly 1"):
        control.change(
            role=Role.ADMIN, status=AiAutonomyStatus.DISABLED, target_core_pct=Decimal("0.50")
        )


def test_strict_consensus_requires_both_analysts() -> None:
    with pytest.raises(ValueError, match="strict consensus"):
        AiAutonomyControl(codex_enabled=True, claude_enabled=False, require_consensus=True)


def test_an_enabled_analysis_worker_requires_at_least_one_analyst() -> None:
    with pytest.raises(ValueError, match="at least one analyst"):
        AiAutonomyControl(
            status=AiAutonomyStatus.ENABLED,
            codex_enabled=False,
            claude_enabled=False,
            require_consensus=False,
        )
