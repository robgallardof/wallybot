import time

import pyotp
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from apps.api.schemas import Login, SetupStart
from wallybot.infrastructure.settings import Settings
from wallybot.security.crypto import Crypto, digest, matching_step, token


@pytest.fixture
def crypto():
    return Crypto(Fernet.generate_key().decode())


def test_password_hash_and_encryption(crypto):
    hashed = crypto.passwords.hash("long-enough-password")
    assert hashed.startswith("$argon2id$")
    assert crypto.verify_password(hashed, "long-enough-password")
    assert not crypto.verify_password(hashed, "wrong")
    assert not crypto.verify_password("corrupt", "wrong")
    encrypted = crypto.encrypt("TOTP secret")
    assert "TOTP secret" not in encrypted
    assert crypto.decrypt(encrypted) == "TOTP secret"


def test_totp_replay_and_window():
    secret, now = pyotp.random_base32(), int(time.time())
    current = now // 30
    code = pyotp.TOTP(secret).at(now)
    assert matching_step(secret, code, now) == current
    assert matching_step(secret, code, now, current) is None
    assert matching_step(secret, pyotp.TOTP(secret).at((current - 3) * 30), now) is None
    assert matching_step(secret, "１２３４５６", now) is None


def test_csrf_bound_to_session(crypto):
    first, second = token(), token()
    assert crypto.csrf(first) != crypto.csrf(second)
    assert first not in digest(first)


def test_settings_fail_closed():
    kwargs = dict(
        database_url=SecretStr("postgresql+psycopg://localhost/wallybot"),
        encryption_key=SecretStr(Fernet.generate_key().decode()),
        bootstrap_token=SecretStr(token()),
        _env_file=None,
    )
    assert Settings(**kwargs).cookie_name == "wally_session"
    with pytest.raises(ValidationError):
        Settings(**kwargs, environment="production")
    with pytest.raises(ValidationError):
        Settings(**kwargs, origin="http://0.0.0.0:3333")
    with pytest.raises(ValidationError):
        Settings(**kwargs, origin="https://example.com/path", cookie_secure=True)
    assert (
        Settings(
            **kwargs, environment="production", origin="https://example.com", cookie_secure=True
        ).cookie_name
        == "__Host-wally_session"
    )


def test_schema_normalization_and_no_injected_fields():
    assert Login(username="  ADMIN  ", password="x").username == "admin"
    with pytest.raises(ValidationError):
        Login(username="admin", password="x", role="ADMIN")
    with pytest.raises(ValidationError):
        SetupStart(username="admin", password="short", bootstrap_token=token())
