"""Grant wally_api read access to whale_transfer_signals and token_risk_scores.

Same reasoning as 0012_smart_money_api_grant: these tables were only ever written by
wally_worker, and nothing exposed them over HTTP until GET /api/intelligence/whale-flow and
GET /api/intelligence/token-risk.

Revision ID: 0013_intelligence_api_grants
"""

from alembic import op

revision = "0013_intelligence_api_grants"
down_revision = "0012_smart_money_api_grant"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON whale_transfer_signals TO wally_api;
        GRANT SELECT ON token_risk_scores TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT ON whale_transfer_signals FROM wally_api;
        REVOKE SELECT ON token_risk_scores FROM wally_api;
      END IF;
    END $$""")
