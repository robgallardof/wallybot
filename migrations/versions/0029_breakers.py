"""Persistent circuit breaker latches (RISK.md: "Persist latch/reason/time ... a scheduler cannot
silently reset a breaker at midnight").

One mutable row per breaker_type (this system has one account) rather than an event log --
`wallybot.security.auth.audit` already records trip/clear as an event for the audit trail.
`wally_api` is the writer, same reasoning as 0027/0028: only `apps/api` runs the live decision
loop that evaluates and trips these.

Revision ID: 0029_breakers
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_breakers"
down_revision = "0028_execution_api_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "breakers",
        sa.Column("breaker_type", sa.String(24), primary_key=True),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("tripped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True)),
        sa.Column("cleared_by", sa.String(36)),
        sa.CheckConstraint(
            "breaker_type IN ('DAILY_LOSS', 'WEEKLY_LOSS', 'DRAWDOWN', 'RECONCILIATION')"
        ),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON breakers TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("breakers")
