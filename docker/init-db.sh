#!/usr/bin/env bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 \
  -v api_password="$(cat /run/secrets/api_password)" \
  -v worker_password="$(cat /run/secrets/worker_password)" \
  -v scheduler_password="$(cat /run/secrets/scheduler_password)" \
  -v research_password="$(cat /run/secrets/research_password)" <<'SQL'
CREATE ROLE wally_api LOGIN PASSWORD :'api_password';
CREATE ROLE wally_worker LOGIN PASSWORD :'worker_password';
CREATE ROLE wally_scheduler LOGIN PASSWORD :'scheduler_password';
CREATE ROLE wally_research LOGIN PASSWORD :'research_password';
REVOKE ALL ON DATABASE wallybot FROM PUBLIC;
GRANT CONNECT ON DATABASE wallybot TO wally_api, wally_worker, wally_scheduler, wally_research;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO wally_api, wally_worker, wally_scheduler, wally_research;
SQL
