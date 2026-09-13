from uuid import uuid4


class UuidIdGenerator:
    """Implements wallybot.domain.id_generator.IdGenerator (structural, not inherited)."""

    def new_id(self) -> str:
        return str(uuid4())
