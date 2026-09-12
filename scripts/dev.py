"""Start hybrid development and terminate tracked children on exit."""

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    os.chdir(ROOT)
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker-compose.yml",
            "-f",
            "docker-compose.dev.yml",
            "up",
            "-d",
            "--wait",
            "postgres",
            "redis",
        ],
        check=True,
    )
    base = os.environ.copy()
    for name in ("encryption_key", "bootstrap_token", "redis_url"):
        value = (ROOT / ".secrets" / name).read_text().strip().replace("@redis:", "@localhost:")
        base["WALLY_" + name.upper()] = value

    def environment(role: str) -> dict[str, str]:
        env = base.copy()
        if role not in {"owner", "api"}:
            env.pop("WALLY_ENCRYPTION_KEY", None)
            env.pop("WALLY_BOOTSTRAP_TOKEN", None)
        if role == "research":
            env.pop("WALLY_REDIS_URL", None)
        env["WALLY_DATABASE_URL"] = (
            (ROOT / ".secrets" / f"{role}_database_url")
            .read_text()
            .strip()
            .replace("@postgres:", "@localhost:")
        )
        return env

    uv = shutil.which("uv")
    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if not uv or not pnpm:
        raise SystemExit("Install uv and pnpm and add them to PATH.")
    subprocess.run([uv, "run", "alembic", "upgrade", "head"], env=environment("owner"), check=True)
    commands = [
        (
            [
                uv,
                "run",
                "uvicorn",
                "apps.api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--no-access-log",
                "--no-proxy-headers",
                "--loop",
                "wallybot.infrastructure.loop:selector_loop",
            ],
            "api",
            ROOT,
        ),
        ([uv, "run", "python", "-m", "apps.worker"], "worker", ROOT),
        ([uv, "run", "python", "-m", "apps.scheduler"], "scheduler", ROOT),
        ([uv, "run", "python", "-m", "apps.research_worker"], "research", ROOT),
        ([pnpm, "dev"], "api", ROOT / "apps/web"),
    ]
    children: list[subprocess.Popen] = []
    try:
        for command, role, cwd in commands:
            children.append(
                subprocess.Popen(
                    command, cwd=cwd, env=environment(role), start_new_session=os.name != "nt"
                )
            )
        print("WallyBot: http://localhost:3333 — Ctrl+C stops app processes.")
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        print("A development service exited; stopping the remaining application processes.")
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                    )
                else:
                    os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            child.wait(timeout=15)


if __name__ == "__main__":
    main()
