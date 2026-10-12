"""Record what happened after an operator approved an AI proposal.

Also grants the API the shadow-decision evidence it already reads (proposal list) and writes
(simulation, post-approval revalidation); 0014 only granted it to the worker.

Revision ID: 0040_proposal_execution
Revises: 0039_proposal_decision_api_grant
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0040_proposal_execution"
down_revision = "0039_proposal_decision_api_grant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trade_proposals", sa.Column("execution_status", sa.String(length=24)))
    op.add_column("trade_proposals", sa.Column("execution_order_id", sa.String(length=64)))
    op.add_column("trade_proposals", sa.Column("execution_reasons", JSONB))
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT ON shadow_decisions TO wally_api;
        GRANT USAGE ON SEQUENCE shadow_decisions_id_seq TO wally_api;
      END IF;
    END $$""")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE USAGE ON SEQUENCE shadow_decisions_id_seq FROM wally_api;
        REVOKE SELECT, INSERT ON shadow_decisions FROM wally_api;
      END IF;
    END $$""")
    op.drop_column("trade_proposals", "execution_reasons")
    op.drop_column("trade_proposals", "execution_order_id")
    op.drop_column("trade_proposals", "execution_status")
