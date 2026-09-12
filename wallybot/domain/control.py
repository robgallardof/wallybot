from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    VIEWER = "VIEWER"


class Status(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


@dataclass(frozen=True)
class Control:
    environment: str = "PAPER"
    status: Status = Status.RUNNING

    def __post_init__(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("This release supports PAPER only")

    def change(self, status: Status, role: Role) -> "Control":
        if role != Role.ADMIN:
            raise PermissionError("Administrator required")
        return Control(status=status)
