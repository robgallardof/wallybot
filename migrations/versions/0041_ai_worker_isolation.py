"""Limit the native analyst to proposals and its own heartbeat (ADR-017)."""

from alembic import op

revision = "0041_ai_worker_isolation"
down_revision = "0040_proposal_execution"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION public.record_ai_worker_heartbeat(heartbeat_time bigint)
      RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        INSERT INTO public.heartbeats(service, timestamp) VALUES ('ai_worker', heartbeat_time)
        ON CONFLICT (service) DO UPDATE SET timestamp = EXCLUDED.timestamp;
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.record_ai_worker_heartbeat(bigint) FROM PUBLIC")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_ai') THEN
        REVOKE ALL ON order_intents, order_transitions, fills, ledger_accounts,
          ledger_transactions, ledger_postings FROM wally_ai;
        REVOKE ALL ON SEQUENCE order_transitions_id_seq, fills_id_seq,
          ledger_accounts_id_seq, ledger_postings_id_seq FROM wally_ai;
        GRANT EXECUTE ON FUNCTION public.record_ai_worker_heartbeat(bigint) TO wally_ai;
      END IF;
    END $$""")


def downgrade():
    op.execute("DROP FUNCTION public.record_ai_worker_heartbeat(bigint)")
    # Do not restore the superseded direct-execution permissions when rolling back telemetry.
