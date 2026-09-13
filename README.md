# WallyBot

Self-hosted, AI-assisted quantitative research and portfolio platform. Its objective is long-term net portfolio growth subject to capital preservation, measurable evidence, and deterministic risk controls. Profitability is not guaranteed.

WallyBot's target shape is a multi-source financial intelligence, portfolio analysis and controlled trading platform: market data plus wallet/entity intelligence (smart money, whale flows, political and corporate disclosures, on-chain events) feeding an AI strategy layer that may only ever *propose* trades, never place them. A deterministic risk engine, portfolio policy engine and execution engine — none of them AI — are the sole path from a proposal to an order. See [ARCHITECTURE.md](ARCHITECTURE.md)'s "Multi-source intelligence and Smart Money" and "AI strategy layer and TradeProposal" sections for the target design; most of this is not built yet — see Current status below and the [implementation sequence](ARCHITECTURE.md#implementation-sequence) for what exists today.

## Current status

Phase 1 now has an executable foundation: FastAPI, React/TypeScript, PostgreSQL, Redis, Alembic, gateway port 3333, password/TOTP authentication, recovery codes, sessions, ADMIN/VIEWER authorization, persistent PAPER controls, audit events, process heartbeats, tests and encrypted backup verification.

LIVE trading is neither implemented nor enabled. Market data, simulated execution, financial accounting and research engines are later phases. The empty portfolio shows no fabricated returns. See [verification status](docs/stats/testing.md) and [remaining scope](docs/PHASE_1.md).

## Start locally

Requirements: Docker Engine/Desktop with Compose and Python 3.12+. Development and tests also need uv, Node 22+ and pnpm 10.11.

```sh
python scripts/bootstrap.py
docker compose up -d --build
```

Open [http://localhost:3333/setup](http://localhost:3333/setup). Read `.secrets/bootstrap_token` locally, create your administrator and enroll your authenticator. Store the one-time recovery codes. No default account is created. The bootstrap script refuses to overwrite existing secrets or `.env`.

The generated configuration binds only to `127.0.0.1:3333`. PostgreSQL and Redis have no host ports in the standard stack. Production requires an HTTPS origin, secure cookies, the requested `0.0.0.0:3333` binding and verified origin filtering; see [deployment](DEPLOYMENT.md).

## Development and tests

```sh
uv sync --frozen
pnpm --dir apps/web install --frozen-lockfile
uv run python scripts/dev.py
```

Stop the full Docker application before hybrid mode to avoid port 3333 conflicts. Hybrid starts infrastructure with the explicit development override and runs application processes on the host. `scripts/dev.ps1`, `sh scripts/dev.sh` and `make dev` are equivalent entry points.

```sh
uv run pytest tests/unit tests/property
uv run pytest tests/integration
pnpm --dir apps/web exec playwright install chromium
pnpm --dir apps/web test:e2e
uv run ruff check apps wallybot migrations scripts tests
uv run pyright
```

Integration and browser tests create disposable databases and fail rather than skip if Docker is unavailable. On Windows, if the Docker Python client cannot find Docker Desktop, set `DOCKER_HOST=npipe:////./pipe/dockerDesktopLinuxEngine` in the test shell. Browser tests use isolated ports 3334/8001 and never initialize your real administrator.

```sh
uv run python scripts/backup.py create
uv run python scripts/backup.py verify
```

Backups are encrypted in ignored `backups/`; keep `.secrets/backup_key` separately off-host. Verification restores only into disposable PostgreSQL. See the [recovery runbook](docs/runbooks/recovery.md).

## Design documents

| Document | Purpose |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Boundaries, contracts, processes, implementation sequence |
| [DATA.md](DATA.md) | Storage, ledger, consistency, data quality, research reproducibility |
| [SECURITY.md](SECURITY.md) | Authentication, authorization, secrets, research isolation |
| [RISK.md](RISK.md) | Deterministic controls, sizing, emergency semantics |
| [TESTING.md](TESTING.md) | Acceptance gates, invariants, failure testing |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Local/Fedora topology, resources, operations and recovery |
| [Decision records](docs/adr/README.md) | Significant decisions and tradeoffs |
| [Diagrams](docs/diagrams/README.md) | Architecture, decision flow, orders, deployment, data, AI, research, recovery |
| [Phase 1 backlog](docs/PHASE_1.md) | Ordered, reviewable implementation slices |

The next product milestone is Phase 2: deterministic fake market data, Kraken market discovery, validated OHLCV/streaming and the market scanner. Later phases must preserve the risk and promotion gates.
