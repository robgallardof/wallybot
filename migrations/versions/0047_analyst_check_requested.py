"""Add check_requested flag so the operator can trigger a fresh CLI availability check from the UI."""

from alembic import op

revision = "0047_analyst_check_requested"
down_revision = "0046_analyst_context_venue"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE ai_autonomy_control ADD COLUMN check_requested BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade():
    op.execute("ALTER TABLE ai_autonomy_control DROP COLUMN check_requested")
