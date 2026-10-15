"""Add starter_requested flag so the operator can ask the analysts for a first starter buy."""

from alembic import op

revision = "0048_analyst_starter_requested"
down_revision = "0047_analyst_check_requested"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE ai_autonomy_control "
        "ADD COLUMN starter_requested BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute("GRANT UPDATE (starter_requested) ON ai_autonomy_control TO wally_ai")


def downgrade():
    op.execute("REVOKE UPDATE (starter_requested) ON ai_autonomy_control FROM wally_ai")
    op.execute("ALTER TABLE ai_autonomy_control DROP COLUMN starter_requested")
