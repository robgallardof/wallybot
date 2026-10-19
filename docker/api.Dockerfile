FROM ghcr.io/astral-sh/uv:0.12.11 AS uv

FROM python:3.14.8-alpine AS builder
RUN apk upgrade --no-cache
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group research --no-install-project
COPY wallybot ./wallybot
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY apps/scheduler ./apps/scheduler
COPY apps/research_worker ./apps/research_worker
RUN uv sync --frozen --no-dev --no-group research

FROM python:3.14.8-alpine AS runtime
RUN apk upgrade --no-cache && addgroup -g 10001 wally && adduser -D -u 10001 -G wally wally
WORKDIR /app
COPY --from=builder --chown=wally:wally /app /app
COPY --chown=wally:wally migrations ./migrations
COPY --chown=wally:wally alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER wally
CMD ["uvicorn", "apps.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

# --- research variant -----------------------------------------------------------------------
# duckdb (Phase 5 backtesting, wallybot/data/historical_query.py) has no musl/Alpine wheel and
# is prohibitively slow to compile from source in a Docker build -- ADR-012 already flagged this
# exact situation as expected future work: "later numerical/research libraries may justify a
# separate glibc research image when their wheel support requires it." Debian slim was rejected
# for the *default* image in ADR-012 over unresolved OS advisories at the time; using it only for
# the two processes that actually touch DuckDB (api, since Phase 5 Slice 5's POST /api/backtests
# calls it synchronously; research_worker, the process this dependency group is named for) keeps
# that tradeoff scoped instead of reintroducing it everywhere.
FROM python:3.14.8-slim AS research-builder
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY wallybot ./wallybot
COPY apps/__init__.py ./apps/__init__.py
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY apps/scheduler ./apps/scheduler
COPY apps/research_worker ./apps/research_worker
RUN uv sync --frozen --no-dev

FROM python:3.14.8-slim AS runtime-research
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
  && groupadd -g 10001 wally && useradd -M -u 10001 -g wally wally
WORKDIR /app
COPY --from=research-builder --chown=wally:wally /app /app
COPY --chown=wally:wally migrations ./migrations
COPY --chown=wally:wally alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# Pre-created so a fresh named volume mounted here (docker-compose.yml's historical_data, api's
# only writable path under its read_only root fs) inherits wally ownership instead of root's --
# Docker copies an image directory's existing content and ownership into a volume on first mount.
RUN mkdir -p /data/historical && chown wally:wally /data/historical
USER wally
CMD ["uvicorn", "apps.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
