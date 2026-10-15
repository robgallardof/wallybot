"""Record which exchange the real account uses so the analyst studies that venue's market."""

from alembic import op

revision = "0046_analyst_context_venue"
down_revision = "0045_ai_analyst_status"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE analyst_portfolio_context ADD COLUMN venue varchar(16) NOT NULL "
        "DEFAULT 'kraken' CHECK (venue IN ('kraken', 'binance'))"
    )


def downgrade():
    op.execute("ALTER TABLE analyst_portfolio_context DROP COLUMN venue")
