"""Inbound Telegram commands (RISK.md: "Confirmar acciones sensibles con tokens expiran/anti-
replay y MFA web cuando corresponda"). `telegram_config.last_update_id` is the getUpdates cursor;
`telegram_confirmations` holds pending sensitive-command confirmations, one row per request --
never executed directly by Telegram, only through the Admin+fresh-MFA web confirm route.
`wally_api` is the writer, same reasoning as every other apps/api-only table: only that process
has internet egress to poll Telegram.

Revision ID: 0030_telegram_commands
"""

import sqlalchemy as sa
from alembic import op

revision = "0030_telegram_commands"
down_revision = "0029_breakers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("telegram_config", sa.Column("last_update_id", sa.BigInteger()))
    op.create_table(
        "telegram_confirmations",
        sa.Column("confirmation_id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.String(36)),
        sa.CheckConstraint("action IN ('PAUSE', 'RESUME')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON telegram_confirmations TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("telegram_confirmations")
    op.drop_column("telegram_config", "last_update_id")
