"""Default control plane to real-data observation instead of PAPER.

Revision ID: 0022_observe_default
"""

from alembic import op

revision = "0022_observe_default"
down_revision = "0021_provider_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("control_environment_check", "control", type_="check")
    op.create_check_constraint(
        "control_environment_check", "control", "environment IN ('OBSERVE', 'PAPER')"
    )
    op.execute("UPDATE control SET environment = 'OBSERVE' WHERE environment = 'PAPER'")


def downgrade():
    op.execute("UPDATE control SET environment = 'PAPER'")
    op.drop_constraint("control_environment_check", "control", type_="check")
    op.create_check_constraint("control_environment_check", "control", "environment = 'PAPER'")
