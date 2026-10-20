"""Telegram /analyze: a holdings-review request flag and per-asset entry facts for the analysts."""

from alembic import op

revision = "0049_holdings_review"
down_revision = "0048_analyst_starter_requested"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE ai_autonomy_control ADD COLUMN review_requested BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute("GRANT UPDATE (review_requested) ON ai_autonomy_control TO wally_ai")
    # Sanitized like the rest of the row: average entry price and oldest open buy, no order IDs.
    op.execute(
        "ALTER TABLE analyst_portfolio_context "
        "ADD COLUMN positions JSONB NOT NULL DEFAULT '{}'::jsonb"
    )


def downgrade():
    op.execute("ALTER TABLE analyst_portfolio_context DROP COLUMN positions")
    op.execute("REVOKE UPDATE (review_requested) ON ai_autonomy_control FROM wally_ai")
    op.execute("ALTER TABLE ai_autonomy_control DROP COLUMN review_requested")
