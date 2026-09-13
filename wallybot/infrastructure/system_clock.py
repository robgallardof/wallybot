from datetime import UTC, datetime


class SystemClock:
    """Implements wallybot.domain.clock.Clock with the real wall clock, for production wiring.

    Every test double so far (FixedClock in tests/contract, tests/unit, tests/property) exists
    specifically to avoid this in tests -- this class is for the one place that actually should
    read the real time: the composition root.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)
