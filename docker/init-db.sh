#!/usr/bin/env bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 \
  -v api_password="$(cat /run/secrets/api_password)" \
  -v worker_password="$(cat /run/secrets/worker_password)" \
  -v scheduler_password="$(cat /run/secrets/scheduler_password)" \
  -v research_password="$(cat /run/secrets/research_password)" \
  -v ai_password="$(cat /run/secrets/ai_password)" <<'SQL'
CREATE ROLE wally_api LOGIN PASSWORD :'api_password';
CREATE ROLE wally_worker LOGIN PASSWORD :'worker_password';
CREATE ROLE wally_scheduler LOGIN PASSWORD :'scheduler_password';
CREATE ROLE wally_research LOGIN PASSWORD :'research_password';
-- wally_ai: used by apps/ai_worker, a native host process (not a container) that invokes the
-- user's own claude/codex CLI. Connects over the loopback-only port docker-compose exposes for
-- Postgres -- see .ai/DECISIONS.md (2026-09-23).
CREATE ROLE wally_ai LOGIN PASSWORD :'ai_password';
REVOKE ALL ON DATABASE wallybot FROM PUBLIC;
GRANT CONNECT ON DATABASE wallybot
  TO wally_api, wally_worker, wally_scheduler, wally_research, wally_ai;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public
  TO wally_api, wally_worker, wally_scheduler, wally_research, wally_ai;
SQL
