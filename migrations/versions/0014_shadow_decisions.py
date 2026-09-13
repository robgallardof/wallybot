"""Shadow decisions: insert-only audit trail for SHADOW-mode allocation/risk outcomes.

Revision ID: 0014_shadow_decisions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014_shadow_decisions"
down_revision = "0013_intelligence_api_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "shadow_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.String(64), nullable=False, index=True),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("base", sa.String(16), nullable=False),
        sa.Column("quote", sa.String(16), nullable=False),
        sa.Column("allocation_approved", sa.Boolean, nullable=False),
        sa.Column("allocation_reasons", JSONB, nullable=False),
        sa.Column("risk_decision", sa.String(32)),
        sa.Column("risk_final_notional", sa.Numeric),
        sa.Column("risk_final_quantity", sa.Numeric),
        sa.Column("risk_reasons", JSONB),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint(
            "risk_decision IS NULL OR "
            "risk_decision IN ('APPROVED', 'REJECTED', 'APPROVED_WITH_REDUCED_SIZE')"
        ),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON shadow_decisions TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("shadow_decisions")
