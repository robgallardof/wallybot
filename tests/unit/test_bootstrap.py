"""Verify fresh-install role secrets using real files and the bootstrap child process."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_bootstrap_provides_required_ai_role_and_preserves_existing_install(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap.py"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    executable = scripts / "bootstrap.py"
    shutil.copyfile(source, executable)
    (tmp_path / ".env.example").write_text("WALLY_ORIGIN=http://localhost:3333\n")
    try:
        created = subprocess.run(
            [sys.executable, str(executable)], cwd=tmp_path, capture_output=True, check=True
        )
        password = (tmp_path / ".secrets" / "ai_password").read_bytes()
        url = (tmp_path / ".secrets" / "ai_database_url").read_bytes()
        assert len(password) >= 32
        assert url == b"postgresql+psycopg://wally_ai:" + password + b"@postgres:5432/wallybot"
        assert password not in created.stdout
        assert password not in created.stderr

        repeated = subprocess.run(
            [sys.executable, str(executable)], cwd=tmp_path, capture_output=True
        )
        assert repeated.returncode != 0
        assert b"refusing to overwrite" in repeated.stderr
        assert (tmp_path / ".secrets" / "ai_password").read_bytes() == password
    finally:
        # The test owns these generated files; release Windows' read-only attribute.
        for file in (tmp_path / ".secrets").glob("*"):
            os.chmod(file, 0o600)
