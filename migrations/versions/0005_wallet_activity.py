"""Wallet activity events: the ingested, deduplicated on-chain observation log
`WalletMonitoringService` (Phase 10 Slice 5) writes to.

Revision ID: 0005_wallet_activity
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_wallet_activity"
down_revision = "0004_relationships"
branch_labels = None
depends_on = None

_ACTIONS = (
    "'BUY', 'SELL', 'SWAP', 'TRANSFER', 'MINT', 'BURN', 'ADD_LIQUIDITY', 'REMOVE_LIQUIDITY', "
    "'APPROVE', 'STAKE', 'UNSTAKE', 'BRIDGE'"
)


def upgrade():
    op.create_table(
        "wallet_activity_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chain", sa.String(32), nullable=False, index=True),
        sa.Column("address", sa.String(128), nullable=False, index=True),
        sa.Column("transaction_hash", sa.String(128), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric, nullable=False),
        sa.Column("value_usd", sa.Numeric),
        sa.Column("price", sa.Numeric),
        sa.Column("liquidity_usd", sa.Numeric),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("attribution_source", sa.String(64), nullable=False),
        sa.Column("attribution_source_entity_id", sa.String(100)),
        sa.Column("attribution_confidence", sa.Numeric, nullable=False),
        sa.Column("attribution_evidence", sa.Text, nullable=False),
        sa.Column("attribution_verification_status", sa.String(16), nullable=False),
        sa.Column("attribution_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
        sa.UniqueConstraint(
            "chain",
            "address",
            "transaction_hash",
            "token",
            "action",
            name="uq_wallet_activity_events_dedup",
        ),
        sa.CheckConstraint(f"action IN ({_ACTIONS})"),
        sa.CheckConstraint("amount > 0"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT ON wallet_activity_events TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("wallet_activity_events")
