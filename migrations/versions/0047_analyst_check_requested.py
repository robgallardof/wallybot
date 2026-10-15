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
    op.execute("GRANT UPDATE (check_requested) ON ai_autonomy_control TO wally_ai")


def downgrade():
    op.execute("REVOKE UPDATE (check_requested) ON ai_autonomy_control FROM wally_ai")
    op.execute("ALTER TABLE ai_autonomy_control DROP COLUMN check_requested")
