"""let the API record operator proposal decisions

Revision ID: 0039_proposal_decision_api_grant
Revises: 0038_ai_proposal_digests
"""

from alembic import op

revision = "0039_proposal_decision_api_grant"
down_revision = "0038_ai_proposal_digests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """The AI role remains insert-only; only the MFA-gated API may record a decision."""
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, UPDATE ON trade_proposals TO wally_api;
      END IF;
    END $$""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT, UPDATE ON trade_proposals FROM wally_api;
      END IF;
    END $$""")
