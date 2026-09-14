"""Grant wally_api SELECT+INSERT on experiment_records, plus USAGE on its id sequence.

Same recurring gap as 0012/0013/0016: this table was only ever granted to wally_worker/
wally_research (0015) before anything exposed it over HTTP. POST /api/backtests now persists a
fresh ExperimentRecord per run (insert-only, same as the other two roles already have) and
GET /api/backtests reads history back.

The sequence grant is new territory for this migration family: every other insert-only table
wally_api has ever been granted onto (events, entities, order_intents, ...) uses an app-generated
string ID, never a Postgres-generated one -- experiment_records is the first with a plain
Integer/autoincrement surrogate `id` column (its real business key is the unique `experiment_id`
string). GRANT INSERT on the table does not by itself include USAGE on the sequence backing that
column's nextval() default; without it, an INSERT via wally_api fails with "permission denied for
sequence experiment_records_id_seq" even though the table grant looks sufficient.

Revision ID: 0017_backtest_api_grants
"""

from alembic import op

revision = "0017_backtest_api_grants"
down_revision = "0016_provider_price_api_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT ON experiment_records TO wally_api;
        GRANT USAGE, SELECT ON SEQUENCE experiment_records_id_seq TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE USAGE, SELECT ON SEQUENCE experiment_records_id_seq FROM wally_api;
        REVOKE SELECT, INSERT ON experiment_records FROM wally_api;
      END IF;
    END $$""")
