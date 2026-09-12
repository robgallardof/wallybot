import hashlib
import hmac
import secrets

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def token() -> str:
    return secrets.token_urlsafe(32)


class Crypto:
    def __init__(self, key: str) -> None:
        self.cipher = Fernet(key.encode())
        self.key = key.encode()
        self.passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
        self.dummy_hash = self.passwords.hash(token())

    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()

    def verify_password(self, stored: str, password: str) -> bool:
        try:
            return self.passwords.verify(stored, password)
        except (VerificationError, InvalidHashError):
            return False

    def csrf(self, session_token: str) -> str:
        return hmac.new(self.key, ("csrf:" + session_token).encode(), hashlib.sha256).hexdigest()


def matching_step(secret: str, code: str, now: int, last_step: int = -1) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    current = now // 30
    totp = pyotp.TOTP(secret)
    for step in (current, current - 1, current + 1):
        if step > last_step and hmac.compare_digest(totp.at(step * 30), code):
            return step
    return None
