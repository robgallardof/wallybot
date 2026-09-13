"""Entity Correlation Graph: one flat, typed-edge relationships table.

Revision ID: 0004_relationships
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_relationships"
down_revision = "0003_intelligence"
branch_labels = None
depends_on = None

_NODE_TYPES = "'WALLET', 'ENTITY', 'TOKEN', 'EVENT', 'TRANSACTION'"
_RELATIONSHIP_TYPES = (
    "'OWNS', 'CONTROLS', 'FUNDS', 'TRADED', 'TRANSFERRED_TO', 'TRANSFERRED_FROM', 'DEPLOYED', "
    "'HOLDS', 'INVESTED_IN', 'RELATED_TO', 'DISCLOSED_TRADE', 'INSIDER_OF'"
)


def upgrade():
    op.create_table(
        "relationships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_type", sa.String(16), nullable=False, index=True),
        sa.Column("source_id", sa.String(128), nullable=False, index=True),
        sa.Column("relationship_type", sa.String(24), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False, index=True),
        sa.Column("target_id", sa.String(128), nullable=False, index=True),
        sa.Column("attribution_source", sa.String(64), nullable=False),
        sa.Column("attribution_source_entity_id", sa.String(100)),
        sa.Column("attribution_confidence", sa.Numeric, nullable=False),
        sa.Column("attribution_evidence", sa.Text, nullable=False),
        sa.Column("attribution_verification_status", sa.String(16), nullable=False),
        sa.Column("attribution_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"source_type IN ({_NODE_TYPES})"),
        sa.CheckConstraint(f"target_type IN ({_NODE_TYPES})"),
        sa.CheckConstraint(f"relationship_type IN ({_RELATIONSHIP_TYPES})"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT, UPDATE ON relationships TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("relationships")
