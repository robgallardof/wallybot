"""AI-autonomous trading toggle: a singleton control row, deliberately separate from `control`
(ControlRow) so pausing the deterministic PAPER loop and enabling/disabling AI-autonomous trading
are two independent switches -- an operator must be able to flip one without the other's
semantics leaking in.

Fails closed: starts DISABLED on every environment, never opt-out-by-migration, same convention
as `control`'s own default row (0001_foundation). Tier targets (`target_core_pct`/
`target_growth_pct`/`target_speculative_pct`) and `digest_interval_hours` are operator-configured
guidance passed into the AI's prompt/context -- soft investment guidance, never an enforced check
(see wallybot/application/ai_decision_loop.py's own module docstring and
docs/adr/016-ai-autonomous-account.md, 2026-09-23, for why this path has no enforced
risk/allocation limits at all).

Revision ID: 0033_ai_autonomy_control
"""

import sqlalchemy as sa
from alembic import op

revision = "0033_ai_autonomy_control"
down_revision = "0032_telegram_pairing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_autonomy_control",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("target_core_pct", sa.Numeric, nullable=False),
        sa.Column("target_growth_pct", sa.Numeric, nullable=False),
        sa.Column("target_speculative_pct", sa.Numeric, nullable=False),
        sa.Column("digest_interval_hours", sa.Integer, nullable=False),
        sa.CheckConstraint("id = 1"),
        sa.CheckConstraint("status IN ('DISABLED', 'ENABLED')"),
    )
    op.execute(
        "INSERT INTO ai_autonomy_control VALUES (1, 'DISABLED', 0.70, 0.20, 0.10, 6)"
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, UPDATE ON ai_autonomy_control TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        REVOKE SELECT, UPDATE ON ai_autonomy_control FROM wally_api;
      END IF;
    END $$""")
    op.drop_table("ai_autonomy_control")
