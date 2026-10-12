from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    VIEWER = "VIEWER"


class Status(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class Environment(StrEnum):
    OBSERVE = "OBSERVE"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class Control:
    environment: Environment = Environment.OBSERVE
    status: Status = Status.RUNNING

    def __post_init__(self) -> None:
        if self.environment not in set(Environment):
            raise ValueError("unknown environment")

    def change(
        self, status: Status, role: Role, environment: Environment | None = None
    ) -> "Control":
        if role != Role.ADMIN:
            raise PermissionError("Administrator required")
        return Control(environment=environment or self.environment, status=status)
