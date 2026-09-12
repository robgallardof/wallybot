from typing import Protocol


class IdGenerator(Protocol):
    """Injectable ID source, so writes stay reproducible in tests instead of using uuid4()."""

    def new_id(self) -> str: ...
