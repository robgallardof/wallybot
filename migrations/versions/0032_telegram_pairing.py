"""Securely bind a Telegram chat after a token-only setup.

The persisted value is a SHA-256 digest of the one-time `/start` code, not the code itself.
Only the API process can read/update this singleton table and it is the sole process permitted
to call Telegram.

Revision ID: 0032_telegram_pairing
"""

import sqlalchemy as sa
from alembic import op

revision = "0032_telegram_pairing"
down_revision = "0031_telegram_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("telegram_config", sa.Column("pairing_code_hash", sa.String(64)))


def downgrade():
    op.drop_column("telegram_config", "pairing_code_hash")
