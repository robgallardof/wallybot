import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wallybot.domain.control import Status


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.@+-]{3,100}", value):
            raise ValueError("Use 3–100 letters, digits or . _ @ + -")
        return value


class SetupStart(Login):
    bootstrap_token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class Verification(Input):
    challenge: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=6, max_length=128)


class SetupFinish(Verification):
    bootstrap_token: str = Field(min_length=32, max_length=256)


class ControlChange(Input):
    status: Status
