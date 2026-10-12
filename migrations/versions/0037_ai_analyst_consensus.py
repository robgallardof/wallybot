"""Configure independent local analysts and strict-consensus mode.

Revision ID: 0037_ai_analyst_consensus
Revises: 0036_proposal_owner
"""

import sqlalchemy as sa
from alembic import op

revision = "0037_ai_analyst_consensus"
down_revision = "0036_proposal_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_autonomy_control",
        sa.Column("codex_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ai_autonomy_control",
        sa.Column("claude_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "ai_autonomy_control",
        sa.Column("require_consensus", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("ai_autonomy_control", "codex_enabled", server_default=None)
    op.alter_column("ai_autonomy_control", "claude_enabled", server_default=None)
    op.alter_column("ai_autonomy_control", "require_consensus", server_default=None)


def downgrade() -> None:
    op.drop_column("ai_autonomy_control", "require_consensus")
    op.drop_column("ai_autonomy_control", "claude_enabled")
    op.drop_column("ai_autonomy_control", "codex_enabled")
