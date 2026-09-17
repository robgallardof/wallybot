"""Grant the API read access needed for the signed-in PAPER portfolio.

Revision ID: 0026_portfolio_api_read_grants
"""

from alembic import op

revision = "0026_portfolio_api_read_grants"
down_revision = "0025_price_consensus_api_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON fills, ledger_accounts, ledger_transactions, ledger_postings TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT ON fills, ledger_accounts, ledger_transactions, ledger_postings
          FROM wally_api;
      END IF;
    END $$""")
