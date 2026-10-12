# Foundation backup and recovery

The implementation currently stores identity, control, events and maintenance state. Financial ledgers do not exist yet. The target RPO/RTO in DEPLOYMENT is not an achieved guarantee.

## Back up and rehearse

With the local stack running and development dependencies installed:

```sh
uv run python scripts/backup.py create
uv run python scripts/backup.py verify
```

Create reads a consistent PostgreSQL custom dump, configuration and individual secret files, then encrypts the archive with a separate Fernet backup key. The backup key is excluded from the archive and is never mounted in app containers. Store encrypted archives off-host and escrow that key separately. Losing the key loses the backup. Never publish `.secrets` or backup plaintext.

Verify authenticates/decrypts the newest archive, restores it into Testcontainers PostgreSQL, checks that the schema revision is one this checkout knows and that the control mode is OBSERVE, PAPER or LIVE, and records the revision, core/ledger row counts and elapsed time in `backups/restore-verification.json`. No restore writes to the operational database. The current tool is for small foundation databases; a 256 MiB dump limit is checked after capture, so it is not a streaming solution. Use streaming backup tooling before datasets grow.

## Restore a real installation

Stop API, scheduler, worker and research; preserve the original database volume for investigation. Restore into a new isolated volume/database first using a compatible PostgreSQL version. Recreate the runtime roles with the backed-up role credentials, restore the custom dump with no owner/ACL assignment, and reapply the grants/policies specified by the installed migration (Alembic will not rerun an already-applied revision).

Recover configuration and encryption key from the authenticated archive through an offline operator process; do not extract untrusted archive paths. Validate schema and account data, revoke restored sessions, confirm PAPER and PAUSED, then start compatible application images and verify readiness. Keep the gateway inaccessible externally during the procedure. Rehearse on the isolated restore target before replacing the operational volume. Automated destructive restore is intentionally not provided.

When execution exists in later phases, exchange reconciliation of the missing interval is mandatory before rearming. Restoring an old pending intent is never permission to submit it again.

## Credential recovery

For a lost authenticator, sign in with the password and one of the eight single-use recovery codes. Using a recovery code revokes earlier sessions. Automated MFA replacement/reset and password reset are not available yet; retain authenticator enrollment and recovery codes securely. Do not reopen `/setup` by editing control state: the disabled endpoint is not an account-recovery mechanism.
