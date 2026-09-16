"""Durable lifecycle metadata for isolated research jobs.

Revision ID: 0020_research_job_queue
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_research_job_queue"
down_revision = "0019_historical_ingestion_cursor"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "jobs",
        sa.Column("payload", sa.dialects.postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "jobs",
        sa.Column("cancel_requested", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column("jobs", sa.Column("claimed_at", sa.BigInteger))
    op.add_column("jobs", sa.Column("completed_at", sa.BigInteger))
    op.add_column("jobs", sa.Column("artifact_uri", sa.Text))
    op.add_column("jobs", sa.Column("error", sa.Text))
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_research') THEN
        GRANT SELECT, UPDATE ON jobs TO wally_research;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON jobs TO wally_api;
      END IF;
    END $$""")


def downgrade():
    for name in (
        "error",
        "artifact_uri",
        "completed_at",
        "claimed_at",
        "cancel_requested",
        "payload",
    ):
        op.drop_column("jobs", name)
