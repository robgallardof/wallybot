"""Sanitized portfolio snapshot for the proposal-only analyst."""

from alembic import op

revision = "0044_analyst_portfolio_context"
down_revision = "0043_live_control"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE analyst_portfolio_context (
      owner_id varchar(36) PRIMARY KEY REFERENCES users(id),
      cash_usd numeric NOT NULL CHECK (cash_usd >= 0),
      holdings jsonb NOT NULL,
      as_of timestamptz NOT NULL)""")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON analyst_portfolio_context TO wally_api;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wally_ai') THEN
        GRANT SELECT ON analyst_portfolio_context TO wally_ai;
      END IF;
    END $$""")


def downgrade():
    op.execute("DROP TABLE analyst_portfolio_context")
