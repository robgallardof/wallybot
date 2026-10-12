"""Scope AI proposals to the operator who owns their mandate and portfolio.

Revision ID: 0036_proposal_owner
Revises: 0035_proposal_decisions
"""

import sqlalchemy as sa
from alembic import op

revision = "0036_proposal_owner"
down_revision = "0035_proposal_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_proposals", sa.Column("owner_id", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_trade_proposals_owner_id_users", "trade_proposals", "users", ["owner_id"], ["id"]
    )
    op.create_index("ix_trade_proposals_owner_id", "trade_proposals", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_trade_proposals_owner_id", table_name="trade_proposals")
    op.drop_constraint("fk_trade_proposals_owner_id_users", "trade_proposals", type_="foreignkey")
    op.drop_column("trade_proposals", "owner_id")
