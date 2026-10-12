"""AiAutonomyControl: the toggle gating periodic AI analysis.

Deliberately separate from `wallybot.domain.control.Control` -- pausing the deterministic PAPER
loop and enabling/disabling AI analysis are two independent switches; an operator must
be able to flip one without the other's semantics leaking into the other. Fails closed
(`AiAutonomyStatus.DISABLED` is the default), matching `Control`'s own conservative default.

Tier targets and the digest interval are operator-configured guidance passed into the AI context.
This type validates that percentages sum to one and cadence is positive. The worker only creates
proposals; an approval and separate mandate/risk validation are required before PAPER execution.
See `docs/adr/017-approved-ai-proposals.md`.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.control import Role


class AiAutonomyStatus(StrEnum):
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


@dataclass(frozen=True)
class AiAutonomyControl:
    status: AiAutonomyStatus = AiAutonomyStatus.DISABLED
    target_core_pct: Decimal = Decimal("0.70")
    target_growth_pct: Decimal = Decimal("0.20")
    target_speculative_pct: Decimal = Decimal("0.10")
    digest_interval_hours: int = 6
    codex_enabled: bool = True
    claude_enabled: bool = True
    require_consensus: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("target_core_pct", self.target_core_pct),
            ("target_growth_pct", self.target_growth_pct),
            ("target_speculative_pct", self.target_speculative_pct),
        ):
            if not (Decimal(0) <= value <= Decimal(1)):
                raise ValueError(f"{name} must be between 0 and 1")
        total = self.target_core_pct + self.target_growth_pct + self.target_speculative_pct
        if total != Decimal(1):
            raise ValueError("tier targets must sum to exactly 1")
        if self.digest_interval_hours <= 0:
            raise ValueError("digest_interval_hours must be positive")
        if self.status == AiAutonomyStatus.ENABLED and not (
            self.codex_enabled or self.claude_enabled
        ):
            raise ValueError("at least one analyst must be enabled before analysis can start")
        if self.require_consensus and not (self.codex_enabled and self.claude_enabled):
            raise ValueError("strict consensus requires both Codex and Claude enabled")

    def change(
        self,
        role: Role,
        status: AiAutonomyStatus,
        target_core_pct: Decimal | None = None,
        target_growth_pct: Decimal | None = None,
        target_speculative_pct: Decimal | None = None,
        digest_interval_hours: int | None = None,
        codex_enabled: bool | None = None,
        claude_enabled: bool | None = None,
        require_consensus: bool | None = None,
    ) -> "AiAutonomyControl":
        if role != Role.ADMIN:
            raise PermissionError("Administrator required")
        return AiAutonomyControl(
            status=status,
            target_core_pct=(
                target_core_pct if target_core_pct is not None else self.target_core_pct
            ),
            target_growth_pct=(
                target_growth_pct if target_growth_pct is not None else self.target_growth_pct
            ),
            target_speculative_pct=(
                target_speculative_pct
                if target_speculative_pct is not None
                else self.target_speculative_pct
            ),
            digest_interval_hours=(
                digest_interval_hours
                if digest_interval_hours is not None
                else self.digest_interval_hours
            ),
            codex_enabled=codex_enabled if codex_enabled is not None else self.codex_enabled,
            claude_enabled=claude_enabled if claude_enabled is not None else self.claude_enabled,
            require_consensus=(
                require_consensus if require_consensus is not None else self.require_consensus
            ),
        )
