"""User-owned provider connection descriptors without credential material.

Revision ID: 0021_provider_connections
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_provider_connections"
down_revision = "0020_research_job_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.UniqueConstraint("user_id", "provider", "label", name="uq_provider_connections_owner"),
        sa.CheckConstraint("mode IN ('READ_ONLY', 'PAPER', 'TRADE_ONLY')"),
        sa.CheckConstraint("status IN ('PENDING', 'HEALTHY', 'UNAVAILABLE')"),
    )
    op.create_index("ix_provider_connections_user_id", "provider_connections", ["user_id"])
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON provider_connections TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("provider_connections")
