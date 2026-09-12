"""Identity, control, audit and process foundation.

Revision ID: 0001_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "control",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("setup_complete", sa.Boolean, nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.CheckConstraint("id = 1"),
        sa.CheckConstraint("environment = 'PAPER'"),
        sa.CheckConstraint("status IN ('RUNNING', 'PAUSED')"),
    )
    op.execute("INSERT INTO control VALUES (1, false, 'PAPER', 'RUNNING')")
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("totp_encrypted", sa.Text, nullable=False),
        sa.Column("last_totp_step", sa.BigInteger, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.CheckConstraint("role IN ('ADMIN', 'VIEWER')"),
    )
    op.create_table(
        "auth_challenges",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("username", sa.String(100)),
        sa.Column("password_hash", sa.Text),
        sa.Column("totp_encrypted", sa.Text),
        sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        *[
            sa.Column(name, sa.BigInteger, nullable=False)
            for name in ("created_at", "last_seen", "mfa_at")
        ],
        sa.Column("expires_at", sa.BigInteger, nullable=False, index=True),
    )
    op.create_table(
        "recovery_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.BigInteger, nullable=False, index=True),
        sa.Column("actor", sa.String(36)),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("message", sa.String(256), nullable=False),
        sa.Column("correlation_id", sa.String(36), nullable=False),
    )
    op.create_table(
        "heartbeats",
        sa.Column("service", sa.String(32), primary_key=True),
        sa.Column("timestamp", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("scheduled_at", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
    )
    # Runtime role exists in Compose, but is absent in isolated Testcontainers by default.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON users, auth_challenges, sessions,
          recovery_codes TO wally_api;
        GRANT SELECT, UPDATE ON control TO wally_api;
        GRANT SELECT, INSERT ON events TO wally_api;
        GRANT SELECT ON heartbeats, alembic_version TO wally_api;
        GRANT SELECT, INSERT, UPDATE, DELETE ON jobs TO wally_worker;
        GRANT SELECT, DELETE ON auth_challenges, sessions TO wally_worker;
        GRANT SELECT, INSERT, UPDATE ON heartbeats TO wally_worker, wally_scheduler;
        GRANT SELECT, INSERT ON jobs TO wally_scheduler;
        GRANT SELECT, INSERT, UPDATE ON heartbeats TO wally_research;
      END IF;
    END $$""")
    op.execute("ALTER TABLE heartbeats ENABLE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY heartbeat_owner ON heartbeats
      USING (current_user = 'wally_' || service)
      WITH CHECK (current_user = 'wally_' || service)""")
    op.execute(
        "CREATE POLICY heartbeat_reader ON heartbeats FOR SELECT USING (current_user = 'wally_api')"
    )


def downgrade():
    for name in (
        "jobs",
        "heartbeats",
        "events",
        "recovery_codes",
        "sessions",
        "auth_challenges",
        "users",
        "control",
    ):
        op.drop_table(name)
