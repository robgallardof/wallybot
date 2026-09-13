"""Grant wally_api read access to smart_money_score_snapshots.

The API role was never granted access to this table because nothing exposed it over HTTP before
`GET /api/intelligence/smart-money` -- only `wally_worker` (which writes scores) had a grant.
Read-only, matching the least-privilege pattern for every other API-readable table.

Revision ID: 0012_smart_money_api_grant
"""

from alembic import op

revision = "0012_smart_money_api_grant"
down_revision = "0011_trade_proposals"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON smart_money_score_snapshots TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT ON smart_money_score_snapshots FROM wally_api;
      END IF;
    END $$""")
