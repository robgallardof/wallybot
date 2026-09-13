"""Trade proposals: insert-only AI advisory audit trail.

Revision ID: 0011_trade_proposals
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011_trade_proposals"
down_revision = "0010_provider_reliability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trade_proposals",
        sa.Column("proposal_id", sa.String(64), primary_key=True),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("base", sa.String(16), nullable=False),
        sa.Column("quote", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("strategy_id", sa.String(64), nullable=False, index=True),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("suggested_allocation_pct", sa.Numeric, nullable=False),
        sa.Column("entry_price", sa.Numeric, nullable=False),
        sa.Column("stop_price", sa.Numeric),
        sa.Column("take_profit_price", sa.Numeric),
        sa.Column("time_horizon_seconds", sa.Numeric, nullable=False),
        sa.Column("signal_ttl_seconds", sa.Numeric, nullable=False),
        sa.Column("reasons", JSONB, nullable=False),
        sa.Column("risks", JSONB, nullable=False),
        sa.Column("supporting_signal_ids", JSONB, nullable=False),
        sa.Column("invalidating_conditions", JSONB, nullable=False),
        sa.Column("source_event_ids", JSONB, nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint("direction IN ('LONG', 'SHORT')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON trade_proposals TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("trade_proposals")
