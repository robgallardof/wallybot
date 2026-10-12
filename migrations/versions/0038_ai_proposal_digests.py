"""Persist AI proposal digest delivery watermarks.

Revision ID: 0038_ai_proposal_digests
Revises: 0037_ai_analyst_consensus
"""

import sqlalchemy as sa
from alembic import op

revision = "0038_ai_proposal_digests"
down_revision = "0037_ai_analyst_consensus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_proposal_digests",
        sa.Column("owner_id", sa.String(length=36), primary_key=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON ai_proposal_digests TO wally_api;
      END IF;
    END $$""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT, INSERT, UPDATE ON ai_proposal_digests FROM wally_api;
      END IF;
    END $$""")
    op.drop_table("ai_proposal_digests")
