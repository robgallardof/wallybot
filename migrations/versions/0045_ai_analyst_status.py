"""Per-analyst CLI availability reported by the native worker; no trading authority."""

from alembic import op

revision = "0045_ai_analyst_status"
down_revision = "0044_analyst_portfolio_context"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE ai_analyst_status (
      analyst varchar(16) PRIMARY KEY CHECK (analyst IN ('codex', 'claude')),
      available boolean NOT NULL,
      checked_at bigint NOT NULL)""")
    op.execute("""CREATE FUNCTION public.record_ai_analyst_status(
        analyst_name text, is_available boolean, check_time bigint)
      RETURNS void LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
        INSERT INTO public.ai_analyst_status(analyst, available, checked_at)
        VALUES (analyst_name, is_available, check_time)
        ON CONFLICT (analyst) DO UPDATE
          SET available = EXCLUDED.available, checked_at = EXCLUDED.checked_at;
      $$""")
    op.execute(
        "REVOKE ALL ON FUNCTION public.record_ai_analyst_status(text, boolean, bigint) FROM PUBLIC"
    )
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_api') THEN
        GRANT SELECT ON ai_analyst_status TO wally_api;
      END IF;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wally_ai') THEN
        GRANT EXECUTE ON FUNCTION public.record_ai_analyst_status(text, boolean, bigint)
          TO wally_ai;
      END IF;
    END $$""")


def downgrade():
    op.execute("DROP FUNCTION public.record_ai_analyst_status(text, boolean, bigint)")
    op.execute("DROP TABLE ai_analyst_status")
