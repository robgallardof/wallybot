from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WALLY_", env_file=".env", extra="ignore")

    environment: Literal["local", "production", "test"] = "local"
    origin: str = "http://localhost:3333"
    database_url: SecretStr
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    encryption_key: SecretStr
    bootstrap_token: SecretStr
    cookie_secure: bool = False
    session_idle_seconds: int = 1800
    session_absolute_seconds: int = 43200
    auth_limit: int = 10
    auth_window_seconds: int = 300
    historical_data_root: Path = Path("/data/historical")

    @field_validator("encryption_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        Fernet(value.get_secret_value().encode())
        return value

    @field_validator("bootstrap_token")
    @classmethod
    def strong_bootstrap(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("Bootstrap token must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def secure_configuration(self) -> Self:
        origin = urlsplit(self.origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc:
            raise ValueError("Origin must be an absolute HTTP(S) origin")
        if origin.path or origin.query or origin.fragment or origin.username:
            raise ValueError("Origin cannot contain path, credentials, query or fragment")
        if not self.cookie_secure and (
            self.environment == "production" or origin.hostname not in {"localhost", "127.0.0.1"}
        ):
            raise ValueError("Insecure cookies are allowed only on local loopback")
        if self.environment == "production" and origin.scheme != "https":
            raise ValueError("Production requires HTTPS")
        if not self.database_url.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("PostgreSQL with psycopg is required")
        if min(self.session_idle_seconds, self.auth_limit, self.auth_window_seconds) <= 0:
            raise ValueError("Session and throttle limits must be positive")
        if self.session_absolute_seconds < self.session_idle_seconds:
            raise ValueError("Absolute lifetime cannot be shorter than idle lifetime")
        return self

    @property
    def cookie_name(self) -> str:
        return "__Host-wally_session" if self.cookie_secure else "wally_session"


def load_settings() -> Settings:
    # Docker secret files take precedence. Pydantic owns all environment access.
    secret_dir = Path("/run/secrets")
    names = ("database_url", "redis_url", "encryption_key", "bootstrap_token")
    values = {
        name: (secret_dir / name).read_text().strip()
        for name in names
        if (secret_dir / name).is_file()
    }
    return Settings(**values)  # type: ignore[arg-type]


class ProcessSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WALLY_", env_file=".env", extra="ignore")
    database_url: SecretStr
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    historical_data_root: Path = Path("/data/historical")


def load_process_settings() -> ProcessSettings:
    directory = Path("/run/secrets")
    values = {
        name: (directory / name).read_text().strip()
        for name in ("database_url", "redis_url")
        if (directory / name).is_file()
    }
    return ProcessSettings(**values)  # type: ignore[arg-type]
