"""Order intents, order transitions, fills and the ledger (accounts/transactions/postings).

Revision ID: 0002_execution
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_execution"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_intents",
        sa.Column("client_order_id", sa.String(100), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("environment", sa.String(8), nullable=False),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("base", sa.String(16), nullable=False),
        sa.Column("quote", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("limit_price", sa.Numeric),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("risk_assessment_id", sa.String(64), nullable=False),
        sa.Column("config_versions", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.UniqueConstraint(
            "account_id", "environment", "idempotency_key", name="uq_order_intents_idempotency"
        ),
        sa.CheckConstraint("environment IN ('PAPER', 'LIVE')"),
        sa.CheckConstraint("side IN ('BUY', 'SELL')"),
        sa.CheckConstraint("kind IN ('MARKET', 'LIMIT')"),
        sa.CheckConstraint("quantity > 0"),
    )
    op.create_table(
        "order_transitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "client_order_id",
            sa.String(100),
            sa.ForeignKey("order_intents.client_order_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("from_status", sa.String(24), nullable=False),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "fills",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fill_id", sa.String(100), nullable=False),
        sa.Column(
            "client_order_id",
            sa.String(100),
            sa.ForeignKey("order_intents.client_order_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(8), nullable=False),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("base", sa.String(16), nullable=False),
        sa.Column("quote", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("price", sa.Numeric, nullable=False),
        sa.Column("fee", sa.Numeric, nullable=False),
        sa.Column("fee_currency", sa.String(16), nullable=False),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("venue", "account_id", "environment", "fill_id", name="uq_fills_dedup"),
        sa.CheckConstraint("quantity > 0"),
        sa.CheckConstraint("price > 0"),
        sa.CheckConstraint("fee >= 0"),
    )
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("currency", sa.String(16), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.UniqueConstraint("account_id", "currency", "purpose", name="uq_ledger_accounts"),
        sa.CheckConstraint("purpose IN ('CASH', 'POSITION', 'CLEARING', 'FEE')"),
    )
    op.create_table(
        "ledger_transactions",
        sa.Column("transaction_id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column("reference_id", sa.String(100), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "reference_id", name="uq_ledger_transactions_dedup"),
    )
    op.create_table(
        "ledger_postings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "transaction_id",
            sa.String(64),
            sa.ForeignKey("ledger_transactions.transaction_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "ledger_account_id", sa.Integer, sa.ForeignKey("ledger_accounts.id"), nullable=False
        ),
        sa.Column("amount", sa.Numeric, nullable=False),
        sa.CheckConstraint("amount <> 0"),
    )
    # Only the trading worker writes execution/ledger state -- the API process stays read-only
    # here until a dashboard slice actually needs to show orders/positions (ARCHITECTURE.md:
    # "separate DB users and grants for migrations, API, trading, scheduling and research").
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_worker') THEN
        GRANT SELECT, INSERT, UPDATE ON order_intents, order_transitions, fills,
          ledger_accounts, ledger_transactions, ledger_postings TO wally_worker;
      END IF;
    END $$""")


def downgrade():
    for name in (
        "ledger_postings",
        "ledger_transactions",
        "ledger_accounts",
        "fills",
        "order_transitions",
        "order_intents",
    ):
        op.drop_table(name)
