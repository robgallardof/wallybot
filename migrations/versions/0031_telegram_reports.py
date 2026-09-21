"""Tracks whether the daily/weekly Telegram report (PENDING.md Fase 8: "Generar reportes
diarios/semanales con rendimiento neto, costes, benchmarks, riesgos y problemas de servicio.")
has already been sent for the current period -- one row per `period`, keyed by `last_sent_key`
('YYYY-MM-DD' for daily, ISO 'YYYY-Www' for weekly) so a restart or a faster loop tick never
resends the same day's/week's report. `wally_api` is the writer, same reasoning as every other
apps/api-only table: only that process has internet egress to reach Telegram.

Revision ID: 0031_telegram_reports
"""

import sqlalchemy as sa
from alembic import op

revision = "0031_telegram_reports"
down_revision = "0030_telegram_commands"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "telegram_reports",
        sa.Column("period", sa.String(16), primary_key=True),
        sa.Column("last_sent_key", sa.String(16), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("period IN ('DAILY', 'WEEKLY')"),
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT, INSERT, UPDATE ON telegram_reports TO wally_api;
      END IF;
    END $$""")


def downgrade():
    op.drop_table("telegram_reports")
