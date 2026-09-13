"""Smart Money score snapshots: insert-only score history.

Revision ID: 0006_smart_money
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_smart_money"
down_revision = "0005_wallet_activity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "smart_money_score_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("wallet_id", sa.String(128), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("score", sa.Numeric),
        sa.Column("trade_count", sa.Integer, nullable=False),
        sa.Column("win_rate", sa.Numeric),
        sa.Column("realized_pnl_usd", sa.Numeric),
        sa.Column("wallet_age_seconds", sa.Numeric),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("reasons", JSONB, nullable=False),
        sa.CheckConstraint("status IN ('SCORED', 'INSUFFICIENT_DATA')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON smart_money_score_snapshots TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("smart_money_score_snapshots")
