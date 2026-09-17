"""Grant wally_api write access to order/fill/ledger tables.

0002's own comment assumed "only the trading worker writes execution/ledger state ... until a
dashboard slice actually needs to show orders/positions" -- but `wally_worker`/`scheduler`/
`research` are on the `internal: true` Docker network with no internet egress (the same
architectural fact 0025/0027 already grant around for price-consensus/equity), so the live
decision loop that actually calls `ExecutionService` has to run inside `apps/api` instead, same as
every other network-dependent job this session's history describes. `apps/api/portfolio_routes.py`
also gained a one-time initial-funding route that writes a ledger transaction directly.

`wally_worker`'s own existing grant (0002) is left untouched -- this is additive, matching every
prior grants-only migration in this history (0016/0017/0018/0023/0025/0026/0027).

Revision ID: 0028_execution_api_grants
"""

from alembic import op

revision = "0028_execution_api_grants"
down_revision = "0027_equity_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON order_intents, order_transitions, fills,
          ledger_accounts, ledger_transactions, ledger_postings TO wally_api;
        GRANT USAGE, SELECT ON order_transitions_id_seq, fills_id_seq,
          ledger_accounts_id_seq, ledger_postings_id_seq TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE USAGE, SELECT ON order_transitions_id_seq, fills_id_seq,
          ledger_accounts_id_seq, ledger_postings_id_seq FROM wally_api;
        REVOKE SELECT, INSERT, UPDATE ON order_intents, order_transitions, fills,
          ledger_accounts, ledger_transactions, ledger_postings FROM wally_api;
      END IF;
    END $$""")
