"""Historical ingestion cursor: tracks per-instrument/timeframe progress for the market data
Parquet ingestion job (wallybot.application.market_ingestion) so a periodic re-fetch of an
overlapping window never re-writes a partition HistoricalStore already published.

Revision ID: 0019_historical_ingestion_cursor
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_historical_ingestion_cursor"
down_revision = "0018_wallet_relationship_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_ingestion_cursors",
        sa.Column("instrument_id", sa.String(128), primary_key=True),
        sa.Column("timeframe", sa.String(16), primary_key=True),
        sa.Column("last_close_time", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON historical_ingestion_cursors TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("historical_ingestion_cursors")
