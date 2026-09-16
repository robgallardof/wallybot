"""Frontend-only server for browser specs with fully intercepted API requests."""

import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js required")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("WALLY_")}
    # Never fall through to the user's running backend.
    env["WALLY_DEV_API"] = "http://127.0.0.1:1"
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    child = subprocess.Popen(
        [
            node,
            str(root / "apps/web/node_modules/next/dist/bin/next"),
            "dev",
            "--hostname",
            "127.0.0.1",
            "--port",
            "3334",
        ],
        cwd=root / "apps/web",
        env=env,
    )
    try:
        raise SystemExit(child.wait())
    finally:
        child.terminate()
        child.wait()


if __name__ == "__main__":
    main()
