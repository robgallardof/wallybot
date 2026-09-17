"""Persistent equity history for daily/weekly loss and drawdown (RISK.md: "Persist boundaries and
high-water marks so restarting cannot reset losses").

`wally_api` is the writer, same reasoning as 0025's price-consensus grants: only `apps/api` has
internet egress to run the live decision loop that computes equity from real market data, so
`worker`/`scheduler`/`research` never touch this table.

Revision ID: 0027_equity_snapshots
"""

import sqlalchemy as sa
from alembic import op

revision = "0027_equity_snapshots"
down_revision = "0026_portfolio_api_read_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "equity_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(8), nullable=False),
        sa.Column("equity", sa.Numeric, nullable=False),
        sa.Column("high_water_mark", sa.Numeric, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("environment IN ('PAPER', 'LIVE')"),
        sa.CheckConstraint("equity > 0"),
        sa.CheckConstraint("high_water_mark >= equity"),
    )
    op.create_index("ix_equity_snapshots_account_id", "equity_snapshots", ["account_id"])
    op.create_index("ix_equity_snapshots_recorded_at", "equity_snapshots", ["recorded_at"])
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT ON equity_snapshots TO wally_api;
        GRANT USAGE, SELECT ON equity_snapshots_id_seq TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("equity_snapshots")
