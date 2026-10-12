"""Encrypted foundation backup and restore verification into a disposable PostgreSQL."""

import argparse
import io
import json
import os
import secrets
import subprocess
import tarfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / "backups"


def backup_key() -> bytes:
    path = ROOT / ".secrets" / "backup_key"
    if not path.exists():
        with path.open("xb") as handle:
            handle.write(Fernet.generate_key())
        os.chmod(path, 0o600)
    return path.read_bytes().strip()


def create() -> Path:
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dump = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "wally_owner",
            "-d",
            "wallybot",
            "-Fc",
            "--no-owner",
            "--no-acl",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    # Foundation-only backup; historical datasets require streaming backup tooling.
    if len(dump) > 256 * 1024 * 1024:
        raise SystemExit("Backup exceeds foundation size limit; use streaming backup tooling.")
    key = backup_key()
    files = {
        "database.dump": dump,
        "metadata.json": json.dumps(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "release": "0.1.0",
                "schema": "0001_foundation",
                "environment": "PAPER",
            }
        ).encode(),
    }
    for path in (ROOT / ".secrets").iterdir():
        if path.is_file() and path.name != "backup_key":
            files[f"secrets/{path.name}"] = path.read_bytes()
    files["configuration.env"] = (ROOT / ".env").read_bytes()
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o600
            tar.addfile(info, io.BytesIO(data))
    destination = BACKUPS / (
        datetime.now(UTC).strftime("wally-%Y%m%dT%H%M%S-") + secrets.token_hex(3) + ".enc"
    )
    with destination.open("xb") as handle:
        handle.write(Fernet(key).encrypt(archive.getvalue()))
    os.chmod(destination, 0o600)
    print(
        f"Encrypted backup written: {destination.name}. Store the backup key separately off-host."
    )
    return destination


def known_revisions() -> set[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    return {revision.revision for revision in script.walk_revisions()}


def verify(path: Path) -> None:
    import psycopg
    from testcontainers.postgres import PostgresContainer

    started = datetime.now(UTC)
    encrypted = path.read_bytes()
    if len(encrypted) > 512 * 1024 * 1024:
        raise SystemExit("Backup exceeds verification size limit")
    data = Fernet((ROOT / ".secrets/backup_key").read_bytes().strip()).decrypt(encrypted)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = tar.extractfile("database.dump")
        if member is None:
            raise SystemExit("Database dump missing")
        dump = member.read()
    # No application, exchange egress, live credentials or production DB connection is used.
    with PostgresContainer("wallybot-postgres:0.1.0", driver="psycopg") as pg:
        container = pg.get_wrapped_container()
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as tar:
            info = tarfile.TarInfo("restore.dump")
            info.size = len(dump)
            tar.addfile(info, io.BytesIO(dump))
        container.put_archive("/tmp", payload.getvalue())
        result = container.exec_run(
            [
                "pg_restore",
                "-U",
                pg.username,
                "-d",
                pg.dbname,
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "/tmp/restore.dump",
            ]
        )
        if result.exit_code:
            raise SystemExit("Isolated restore failed; inspect the disposable restore environment.")
        with psycopg.connect(pg.get_connection_url().replace("+psycopg", "")) as db:
            revision = db.execute("SELECT version_num FROM alembic_version").fetchone()
            mode = db.execute("SELECT environment FROM control WHERE id=1").fetchone()
            # A restore must land on a revision this checkout knows and a valid control mode.
            if (
                revision is None
                or revision[0] not in known_revisions()
                or mode is None
                or mode[0] not in {"OBSERVE", "PAPER", "LIVE"}
            ):
                raise SystemExit("Restored state failed verification")
            counts = {
                name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in (
                    "users",
                    "events",
                    "sessions",
                    "jobs",
                    "trade_proposals",
                    "order_intents",
                    "fills",
                    "ledger_transactions",
                )
            }
    report = {
        "backup": path.name,
        "verified_at": datetime.now(UTC).isoformat(),
        "seconds": (datetime.now(UTC) - started).total_seconds(),
        "revision": revision[0],
        "rows": counts,
        "result": "PASS",
        "scope": "schema revision, control mode and core/ledger row counts",
    }
    (BACKUPS / "restore-verification.json").write_text(json.dumps(report, indent=2))
    print("Isolated restore verification passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "verify"])
    args = parser.parse_args()
    if args.action == "create":
        create()
    else:
        candidates = sorted(BACKUPS.glob("*.enc"))
        if not candidates:
            raise SystemExit("No encrypted backups found")
        verify(candidates[-1])
