"""Smart Money cluster signals: insert-only detection history.

Revision ID: 0007_smart_money_clusters
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_smart_money_clusters"
down_revision = "0006_smart_money"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "smart_money_cluster_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(64), nullable=False, index=True),
        sa.Column("chain", sa.String(32), nullable=False, index=True),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("wallet_ids", JSONB, nullable=False),
        sa.Column("independent_wallet_count", sa.Integer, nullable=False),
        sa.Column("total_value_usd", sa.Numeric, nullable=False),
        sa.Column("average_entry_price", sa.Numeric, nullable=False),
        sa.Column("independence_score", sa.Numeric, nullable=False),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("reasons", JSONB, nullable=False),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON smart_money_cluster_signals TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("smart_money_cluster_signals")
