"""Least-privilege grants for `wally_ai` -- the DB role used by `apps/ai_worker`, a native host
process (not a Docker container, unlike every other role in this file) that invokes the user's
own already-authenticated `claude`/`codex` CLI to drive the AI-autonomous PAPER trading path
recorded in `docs/adr/016-ai-autonomous-account.md` (2026-09-23).

Grants mirror exactly what `wally_api` already needs for the identical `ExecutionService`/
`TradeProposalRepository` call paths (0028_execution_api_grants, 0011_trade_proposals) -- this
role calls the same application code, just from a different process. No grant beyond that: no
`credentials`, no `provider_connections`, no research tables, no DELETE/TRUNCATE anywhere.
`wally_ai` is created by `docker/init-db.sh` on a fresh install, or via the documented one-time
manual `CREATE ROLE` step against an already-running instance (see DEPLOYMENT.md) -- role
creation itself is deliberately not a migration, matching every prior role in this history.

Revision ID: 0034_ai_worker_grants
"""

from alembic import op

revision = "0034_ai_worker_grants"
down_revision = "0033_ai_autonomy_control"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_ai') THEN
        GRANT SELECT, INSERT ON trade_proposals TO wally_ai;
        GRANT SELECT, INSERT, UPDATE ON order_intents, order_transitions, fills,
          ledger_accounts, ledger_transactions, ledger_postings TO wally_ai;
        GRANT USAGE, SELECT ON order_transitions_id_seq, fills_id_seq,
          ledger_accounts_id_seq, ledger_postings_id_seq TO wally_ai;
        GRANT SELECT ON control, ai_autonomy_control, users TO wally_ai;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_ai') THEN
        REVOKE SELECT ON control, ai_autonomy_control, users FROM wally_ai;
        REVOKE USAGE, SELECT ON order_transitions_id_seq, fills_id_seq,
          ledger_accounts_id_seq, ledger_postings_id_seq FROM wally_ai;
        REVOKE SELECT, INSERT, UPDATE ON order_intents, order_transitions, fills,
          ledger_accounts, ledger_transactions, ledger_postings FROM wally_ai;
        REVOKE SELECT, INSERT ON trade_proposals FROM wally_ai;
      END IF;
    END $$""")
