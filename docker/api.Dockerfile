FROM ghcr.io/astral-sh/uv:0.12.11 AS uv
FROM python:3.12.14-alpine AS builder
RUN apk upgrade --no-cache
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

FROM python:3.12.14-alpine
RUN apk upgrade --no-cache && addgroup -g 10001 wally && adduser -D -u 10001 -G wally wally
WORKDIR /app
COPY --from=builder --chown=wally:wally /app /app
COPY --chown=wally:wally migrations ./migrations
COPY --chown=wally:wally alembic.ini ./
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER wally
CMD ["uvicorn", "apps.api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
