"""Provider reliability snapshots and price consensus results: insert-only history.

Revision ID: 0010_provider_reliability
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0010_provider_reliability"
down_revision = "0009_whale_transfers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "provider_reliability_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("call_count", sa.Integer, nullable=False),
        sa.Column("error_rate", sa.Numeric),
        sa.Column("average_latency_ms", sa.Numeric),
        sa.Column("seconds_since_last_success", sa.Numeric),
        sa.Column("reasons", JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint("status IN ('HEALTHY', 'DEGRADED', 'UNRELIABLE', 'INSUFFICIENT_DATA')"),
    )
    op.create_table(
        "price_consensus_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("consensus_price", sa.Numeric),
        sa.Column("included_sources", JSONB, nullable=False),
        sa.Column("excluded_sources", JSONB, nullable=False),
        sa.Column("reasons", JSONB, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.CheckConstraint("status IN ('CONSENSUS', 'INSUFFICIENT_DATA')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON provider_reliability_snapshots TO wally_worker;
        GRANT SELECT, INSERT ON price_consensus_results TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("price_consensus_results")
    op.drop_table("provider_reliability_snapshots")
