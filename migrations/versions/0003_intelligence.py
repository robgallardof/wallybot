"""Entity Registry and Wallet Registry: entities, entity attributions, wallets, wallet
attributions, wallet clusters and cluster membership.

Revision ID: 0003_intelligence
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_intelligence"
down_revision = "0002_execution"
branch_labels = None
depends_on = None

_ENTITY_TYPES = (
    "'PERSON', 'PUBLIC_FIGURE', 'POLITICIAN', 'FUND', 'COMPANY', 'EXCHANGE', 'INSTITUTION', "
    "'WHALE', 'TRADER', 'WALLET_CLUSTER', 'ANONYMOUS_WALLET', 'DEVELOPER', 'MARKET_MAKER', "
    "'PROTOCOL', 'ETF', 'GOVERNMENT', 'CUSTOM'"
)


def upgrade():
    op.create_table(
        "entities",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("entity_type", sa.String(24), nullable=False),
        sa.Column("aliases", JSONB, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("trust_score", sa.Numeric, nullable=False),
        sa.Column("risk_score", sa.Numeric, nullable=False),
        sa.Column("influence_weight", sa.Numeric, nullable=False),
        sa.Column("tags", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"entity_type IN ({_ENTITY_TYPES})"),
    )
    op.create_table(
        "entity_attributions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "entity_id", sa.String(64), sa.ForeignKey("entities.id"), nullable=False, index=True
        ),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_entity_id", sa.String(100)),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("verification_status", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "entity_id",
            "source",
            "source_entity_id",
            "observed_at",
            name="uq_entity_attributions_dedup",
        ),
    )
    op.create_table(
        "wallets",
        sa.Column("chain", sa.String(32), primary_key=True),
        sa.Column("address", sa.String(128), primary_key=True),
        sa.Column("entity_id", sa.String(64), sa.ForeignKey("entities.id"), index=True),
        sa.Column("alias", sa.String(200)),
        sa.Column("labels", JSONB, nullable=False),
        sa.Column("tags", JSONB, nullable=False),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("trust_score", sa.Numeric, nullable=False),
        sa.Column("risk_score", sa.Numeric, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("monitoring_mode", sa.String(16), nullable=False),
        sa.Column("influence_weight", sa.Numeric, nullable=False),
        sa.Column("max_signal_weight", sa.Numeric, nullable=False),
        sa.Column("max_allocation", sa.Numeric),
        sa.Column("min_transaction_value", sa.Numeric, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("monitoring_mode IN ('OBSERVE', 'AI_EVALUATED', 'MIRROR')"),
    )
    op.create_table(
        "wallet_attributions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chain", sa.String(32), nullable=False, index=True),
        sa.Column("address", sa.String(128), nullable=False, index=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("source_entity_id", sa.String(100)),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("verification_status", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
        sa.UniqueConstraint(
            "chain",
            "address",
            "source",
            "source_entity_id",
            "observed_at",
            name="uq_wallet_attributions_dedup",
        ),
    )
    op.create_table(
        "wallet_clusters",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("entity_id", sa.String(64), sa.ForeignKey("entities.id"), index=True),
        sa.Column("confidence", sa.Numeric, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "wallet_cluster_members",
        sa.Column(
            "cluster_id", sa.String(64), sa.ForeignKey("wallet_clusters.id"), primary_key=True
        ),
        sa.Column("chain", sa.String(32), primary_key=True),
        sa.Column("address", sa.String(128), primary_key=True),
        sa.ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
    )
    # Research/intelligence infrastructure is OBSERVE-only (ARCHITECTURE.md's Phase 10): the
    # worker that will eventually run monitoring/scoring gets read/write here, same least-
    # privilege pattern as the execution tables in 0002_execution.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT, UPDATE ON entities, entity_attributions, wallets,
          wallet_attributions, wallet_clusters, wallet_cluster_members TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    for name in (
        "wallet_cluster_members",
        "wallet_clusters",
        "wallet_attributions",
        "wallets",
        "entity_attributions",
        "entities",
    ):
        op.drop_table(name)
