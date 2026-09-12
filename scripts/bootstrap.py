"""Generate first-install secrets. Never overwrite an existing installation."""

import base64
import os
import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    directory = root / ".secrets"
    if directory.exists() or (root / ".env").exists():
        raise SystemExit("Existing .secrets or .env detected; refusing to overwrite credentials.")
    directory.mkdir(mode=0o700)
    values: dict[str, str] = {}
    for role in ("owner", "api", "worker", "scheduler", "research"):
        password = secrets.token_urlsafe(32)
        values[f"{role}_password"] = password
        values[f"{role}_database_url"] = (
            f"postgresql+psycopg://wally_{role}:{password}@postgres:5432/wallybot"
        )
    values["redis_password"] = secrets.token_urlsafe(32)
    values["redis_url"] = f"redis://:{values['redis_password']}@redis:6379/0"
    values["encryption_key"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    values["bootstrap_token"] = secrets.token_urlsafe(32)
    for name, value in values.items():
        path = directory / name
        with path.open("x") as handle:
            handle.write(value)
        # Parent is owner-only; mounted individual files must be readable by container UIDs.
        os.chmod(path, 0o444)
    (root / ".env").write_text((root / ".env.example").read_text())
    os.chmod(root / ".env", 0o600)
    print("Local secrets created. Open .secrets/bootstrap_token to complete /setup.")
    print("On Windows, restrict .secrets access to your account using folder permissions.")


if __name__ == "__main__":
    main()
