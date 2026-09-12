from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Injectable time source, so decisions and tests never depend on the wall clock."""

    def now(self) -> datetime: ...
