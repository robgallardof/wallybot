"""Durable signed-request nonces; no LIVE activation or execution grant."""

from alembic import op

revision = "0042_kraken_private_nonce"
down_revision = "0041_ai_worker_isolation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE kraken_nonces (
        key_fingerprint varchar(64) PRIMARY KEY,
        last_nonce bigint NOT NULL CHECK (last_nonce > 0))""")
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON kraken_nonces TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("DROP TABLE kraken_nonces")
