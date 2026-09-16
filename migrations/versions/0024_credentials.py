"""Let a user actually store their own broker/wallet credentials and Telegram bot token.

provider_connections previously stored no credential material at all -- label/mode/status only,
so "adding a connection" was purely cosmetic. Adds two nullable encrypted columns: enough for an
exchange API key+secret or a wallet address (key only). Values are Fernet-encrypted with the same
encryption_key already used for TOTP secrets (wallybot.security.crypto.Crypto); the browser never
receives them back after submission, per ADR-015's "write-only from the browser".

New telegram_config: a singleton row (id=1), same shape as `control`, holding an encrypted bot
token and the operator's chat id. Storing it here does not wire up actually sending
notifications -- that is separate follow-up work.

Revision ID: 0024_credentials
"""

import sqlalchemy as sa
from alembic import op

revision = "0024_credentials"
down_revision = "0023_experiment_precision"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("provider_connections", sa.Column("encrypted_key", sa.Text))
    op.add_column("provider_connections", sa.Column("encrypted_secret", sa.Text))
    op.create_table(
        "telegram_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.CheckConstraint("id = 1"),
        sa.Column("encrypted_bot_token", sa.Text),
        sa.Column("chat_id", sa.BigInteger),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.execute("INSERT INTO telegram_config (id, enabled) VALUES (1, false)")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, UPDATE ON telegram_config TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("telegram_config")
    op.drop_column("provider_connections", "encrypted_secret")
    op.drop_column("provider_connections", "encrypted_key")
