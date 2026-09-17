"""Grant wally_api write access to provider_reliability_snapshots and price_consensus_results.

Same recurring gap 0012/0013/0016/0017/0018/0023 already found (6th time): 0016 granted wally_api
read-only SELECT on these two tables, back when `GET /api/intelligence/provider-reliability`/
`price-consensus` were the only consumers and 0010's docstring assumed `wally_worker` would be the
only writer. `wallybot.application.price_consensus_job` (new) now writes both tables from
`apps/api` instead -- `worker`/`scheduler`/`research` have no internet egress to reach a second
market-data provider, so `wally_api` needs INSERT here, plus USAGE/SELECT on both autoincrement
sequences (an insert with a SERIAL primary key needs the sequence privilege too, per the
`experiment_records_id_seq` gotcha 0023 already documented).

Revision ID: 0025_price_consensus_api_grants
"""

from alembic import op

revision = "0025_price_consensus_api_grants"
down_revision = "0024_credentials"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT INSERT ON provider_reliability_snapshots TO wally_api;
        GRANT INSERT ON price_consensus_results TO wally_api;
        GRANT USAGE, SELECT ON provider_reliability_snapshots_id_seq TO wally_api;
        GRANT USAGE, SELECT ON price_consensus_results_id_seq TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE USAGE, SELECT ON provider_reliability_snapshots_id_seq FROM wally_api;
        REVOKE USAGE, SELECT ON price_consensus_results_id_seq FROM wally_api;
        REVOKE INSERT ON provider_reliability_snapshots FROM wally_api;
        REVOKE INSERT ON price_consensus_results FROM wally_api;
      END IF;
    END $$""")
