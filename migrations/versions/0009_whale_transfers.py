"""Whale transfer signals: insert-only detection history.

Revision ID: 0009_whale_transfers
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_whale_transfers"
down_revision = "0008_token_risk"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "whale_transfer_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("wallet_id", sa.String(128), nullable=False, index=True),
        sa.Column("chain", sa.String(32), nullable=False, index=True),
        sa.Column("token", sa.String(64), nullable=False, index=True),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("amount", sa.Numeric, nullable=False),
        sa.Column("value_usd", sa.Numeric, nullable=False),
        sa.Column("threshold_usd", sa.Numeric, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("reasons", JSONB, nullable=False),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON whale_transfer_signals TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("whale_transfer_signals")
