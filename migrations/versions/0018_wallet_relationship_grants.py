"""Grant wally_api read access to wallet_activity_events and relationships.

Same recurring gap as 0012/0013/0016: these tables were only ever written by wally_worker, and
nothing exposed them over HTTP until GET /api/intelligence/wallet-activity and
GET /api/intelligence/entity-graph.

Revision ID: 0018_wallet_relationship_grants
"""

from alembic import op

revision = "0018_wallet_relationship_grants"
down_revision = "0017_backtest_api_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON wallet_activity_events TO wally_api;
        GRANT SELECT ON relationships TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT ON wallet_activity_events FROM wally_api;
        REVOKE SELECT ON relationships FROM wally_api;
      END IF;
    END $$""")
