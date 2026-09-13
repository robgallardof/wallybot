"""Token risk scores: insert-only score history.

Revision ID: 0008_token_risk
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_token_risk"
down_revision = "0007_smart_money_clusters"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "token_risk_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token_id", sa.String(128), nullable=False, index=True),
        sa.Column("chain", sa.String(32), nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("risk_score", sa.Numeric),
        sa.Column("reasons", JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint("status IN ('SCORED', 'INSUFFICIENT_DATA')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON token_risk_scores TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("token_risk_scores")
