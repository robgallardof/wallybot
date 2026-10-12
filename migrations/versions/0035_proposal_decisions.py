"""proposal decision state

Revision ID: 0035_proposal_decisions
Revises: 0034_ai_worker_grants
"""

import sqlalchemy as sa
from alembic import op

revision = "0035_proposal_decisions"
down_revision = "0034_ai_worker_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "trade_proposals",
        sa.Column("decision_status", sa.String(16), nullable=False, server_default="PENDING"),
    )
    op.add_column(
        "trade_proposals", sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("trade_proposals", "decided_at")
    op.drop_column("trade_proposals", "decision_status")
