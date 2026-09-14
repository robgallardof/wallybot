"""Grant wally_api read access to provider_reliability_snapshots and price_consensus_results.

Same reasoning as 0012/0013: these tables were only ever written by wally_worker, and nothing
exposed them over HTTP until GET /api/intelligence/provider-reliability and
GET /api/intelligence/price-consensus.

Revision ID: 0016_provider_price_api_grants
"""

from alembic import op

revision = "0016_provider_price_api_grants"
down_revision = "0015_experiment_records"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON provider_reliability_snapshots TO wally_api;
        GRANT SELECT ON price_consensus_results TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT ON provider_reliability_snapshots FROM wally_api;
        REVOKE SELECT ON price_consensus_results FROM wally_api;
      END IF;
    END $$""")
