# Data inventory

Implemented tables: control, users, auth_challenges, sessions, recovery_codes, events, heartbeats and jobs, plus Alembic metadata. Runtime times are UTC Unix seconds. Passwords use Argon2id; TOTP secrets are encrypted; session/recovery/challenge tokens are hashed.

No market dataset, financial ledger, exchange account or analytical Parquet partition exists. Empty financial UI values represent unavailable functionality, not measured zero return. Browser and integration fixtures are isolated and disposable.
