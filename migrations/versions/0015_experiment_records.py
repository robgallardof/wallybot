"""Experiment records: insert-only reproducibility record for backtest runs.

Revision ID: 0015_experiment_records
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_experiment_records"
down_revision = "0014_shadow_decisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiment_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("strategy_id", sa.String(64), nullable=False, index=True),
        sa.Column("strategy_version", sa.Integer, nullable=False),
        sa.Column("feature_engine_version", sa.Integer, nullable=False),
        sa.Column("backtest_engine_version", sa.Integer, nullable=False),
        sa.Column("instrument_venue", sa.String(32), nullable=False),
        sa.Column("instrument_base", sa.String(16), nullable=False),
        sa.Column("instrument_quote", sa.String(16), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_window", sa.Integer, nullable=False),
        sa.Column("risk_off_threshold", sa.Numeric, nullable=False),
        sa.Column("fee_rate", sa.Numeric, nullable=False),
        sa.Column("slippage_pct", sa.Numeric, nullable=False),
        sa.Column("starting_equity", sa.Numeric, nullable=False),
        sa.Column("allocation_pct", sa.Numeric, nullable=False),
        sa.Column("seed", sa.BigInteger),
        sa.Column("trade_count", sa.Integer, nullable=False),
        sa.Column("final_equity", sa.Numeric, nullable=False),
        sa.Column("total_return_pct", sa.Numeric, nullable=False),
        sa.Column("max_drawdown_pct", sa.Numeric, nullable=False),
        sa.Column("win_rate", sa.Numeric),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_research') THEN
        GRANT SELECT, INSERT ON experiment_records TO wally_research;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON experiment_records TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("experiment_records")
