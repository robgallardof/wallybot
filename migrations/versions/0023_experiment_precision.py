"""Store the full Instrument identity (market_type + precision) an experiment run actually used.

An isolated research re-run (wallybot.infrastructure.jobs, service=="research") has no internet
egress to call a live exchange adapter's discover_instruments() again -- see
wallybot.domain.experiment's docstring. experiment_records is empty in every environment this
migration runs against (it's a brand-new table from Phase 5, and migrations replay from scratch in
tests/CI), so the new columns are added NOT NULL directly rather than nullable-plus-backfill.

Also grants wally_research USAGE on the id sequence: migration 0015 granted it SELECT/INSERT on
experiment_records but never the sequence backing the autoincrement id column, the same gap 0017
later found and fixed for wally_api. wally_research never successfully inserted a row before this
either -- it just never tried until now.

Revision ID: 0023_experiment_precision

Kept to 26 chars -- alembic_version.version_num is varchar(32); a longer id fails upgrade with
StringDataRightTruncation, the exact known gotcha 0019's own docstring already documents.
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_experiment_precision"
down_revision = "0022_observe_default"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "experiment_records",
        sa.Column("instrument_market_type", sa.String(16), nullable=False),
    )
    op.add_column("experiment_records", sa.Column("price_increment", sa.Numeric, nullable=False))
    op.add_column("experiment_records", sa.Column("quantity_increment", sa.Numeric, nullable=False))
    op.add_column("experiment_records", sa.Column("min_quantity", sa.Numeric, nullable=False))
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_research') THEN
        GRANT USAGE, SELECT ON SEQUENCE experiment_records_id_seq TO wally_research;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_research') THEN
        REVOKE USAGE, SELECT ON SEQUENCE experiment_records_id_seq FROM wally_research;
      END IF;
    END $$""")
    op.drop_column("experiment_records", "min_quantity")
    op.drop_column("experiment_records", "quantity_increment")
    op.drop_column("experiment_records", "price_increment")
    op.drop_column("experiment_records", "instrument_market_type")
