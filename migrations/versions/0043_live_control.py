"""Explicit operator-owned LIVE configuration; disabled until verified activation."""

from alembic import op

revision = "0043_live_control"
down_revision = "0042_kraken_private_nonce"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""DO $$ DECLARE constraint_name text; BEGIN
      SELECT conname INTO constraint_name FROM pg_constraint
      WHERE conrelid = 'control'::regclass AND contype = 'c'
        AND pg_get_constraintdef(oid) LIKE '%environment%';
      IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE control DROP CONSTRAINT %I', constraint_name);
      END IF;
    END $$""")
    op.execute(
        "ALTER TABLE control ADD CONSTRAINT ck_control_environment "
        "CHECK (environment IN ('OBSERVE','PAPER','LIVE'))"
    )
    op.execute("""CREATE TABLE live_control (
      id integer PRIMARY KEY CHECK (id=1),
      owner_id varchar(36) NOT NULL REFERENCES users(id),
      connection_id varchar(36) NOT NULL REFERENCES provider_connections(id),
      enabled boolean NOT NULL DEFAULT false,
      initialized boolean NOT NULL DEFAULT false,
      max_order_usd numeric NOT NULL CHECK (max_order_usd > 0),
      max_daily_loss_usd numeric NOT NULL CHECK (max_daily_loss_usd > 0),
      max_total_usd numeric NOT NULL CHECK (max_total_usd > 0),
      slippage_pct numeric NOT NULL CHECK (slippage_pct > 0 AND slippage_pct <= 0.02),
      version integer NOT NULL DEFAULT 1,
      state varchar(32) NOT NULL DEFAULT 'DISABLED',
      reason varchar(256) NOT NULL DEFAULT '')""")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON live_control TO wally_api;
      END IF;
    END $$""")
    op.execute("ALTER TABLE trade_proposals ADD COLUMN execution_environment varchar(8)")


def downgrade():
    op.execute("UPDATE control SET environment='OBSERVE' WHERE environment='LIVE'")
    op.execute("DROP TABLE live_control")
    op.execute("ALTER TABLE trade_proposals DROP COLUMN execution_environment")
    op.execute("ALTER TABLE control DROP CONSTRAINT ck_control_environment")
    op.execute(
        "ALTER TABLE control ADD CONSTRAINT ck_control_environment "
        "CHECK (environment IN ('OBSERVE','PAPER'))"
    )
