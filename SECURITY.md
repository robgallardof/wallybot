# Security design

Update 2026-10-12: [ADR-018](docs/adr/018-real-spot-objective.md) implements explicit, per-operation
approved Kraken spot LIVE activation. This supersedes the older Phase 1/PAPER-only status below;
unattended strategy promotion and external tamper-evident export remain separate work.

Status: password/TOTP setup, recovery-code login, hashed sessions, CSRF/origin checks, shared throttling, role checks, scoped database grants and isolated research credentials are implemented. Provider secrets, strategy promotion, LIVE activation, MFA replacement and external tamper-evident audit export remain later work. Application authentication remains mandatory behind Cloudflare Zero Trust.

## Trust boundaries and threats

| Threat | Required control |
| --- | --- |
| Origin bypass / forged proxy identity | Restrict origin reachability; trust forwarded headers only from configured proxy; app session and RBAC |
| Remote bootstrap takeover | One-use out-of-band setup token and atomic first-admin transaction |
| Stolen password/session | Argon2id, TOTP, rate limits, revocation, bounded sessions, secure cookies |
| CSRF / XSS | CSRF token plus origin checks, CSP, escaped rendering, no unsafe HTML, HttpOnly cookie |
| Prompt injection / compromised research | Untrusted data, strict schemas, no execution tools or trading secrets, separate process/grants |
| Duplicate/replayed trade request | Durable idempotency, intent-bound risk approval, account reservations, reconciliation |
| Secret leakage / dependency compromise | Restricted secrets, redaction, pinned artifacts, scans, least-privilege containers |
| Insider or runtime configuration change | ADMIN + fresh MFA, versioning, audit, immutable hard limits |

## First boot and authentication

Phase 1 introduces a bootstrap token generated outside the web request and stored as a restricted secret. The operator obtains it through the local setup tool. `/setup` requires this token, is rate limited, and only works while no administrator exists. Stage a provisional account and encrypted TOTP secret; create the active admin, record successful TOTP enrollment and consume bootstrap access in one database-locked transaction. Competing setup requests cannot both win. Disable bootstrap permanently after success; account recovery is a separate local audited procedure.

Normalize usernames/emails; require long passwords, support password managers, reject known compromised passwords when a privacy-preserving checker is configured. Hash with Argon2id, benchmark parameters on target hardware and rehash on upgrade. Login responses avoid account enumeration. Progressive throttling is shared across API instances; authentication and privileged writes fail closed if the required rate-limit store is unavailable.

Password success creates only a short-lived MFA challenge. After TOTP succeeds, issue an opaque high-entropy session token; store only its hash. Record and atomically consume the accepted TOTP time step to prevent concurrent replay, with a small documented clock-skew window. Encrypt TOTP seeds with a key outside the database. Show enrollment material only during setup, never in logs. Recovery codes are single-use hashes; replacing MFA revokes sessions and requires recovery or fresh verified MFA.

Production cookie: HttpOnly, Secure, SameSite=Lax, Path=/, no Domain, preferably `__Host-` prefix. Rotate on authentication and privilege change, revoke on logout/password reset, and use initial 30-minute idle/12-hour absolute expiry. Require recent MFA for secret changes, risk edits, LIVE activation, resumption from a breaker and destructive emergency commands. Insecure-cookie localhost development is explicit, loopback-only, and rejected for a production configuration. Session cookies and MFA handling follow [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) and [MFA guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html).

## Authorization

VIEWER can view redacted dashboards, events and reports. ADMIN can configure and operate within hard policy. Both require MFA. Default deny at each use case; hiding a button is not authorization. Sensitive exports and logs require explicit permissions and redaction. Roles do not grant direct DB or exchange credentials. No public endpoint can submit an arbitrary exchange request or designate its own approval.

LIVE activation requires enabled build/environment capability, validated trade-only exchange permissions with withdrawals disabled, healthy connectivity, fresh successful reconciliation, eligible promoted strategy, valid limits, fresh TOTP and explicit confirmation of account/environment. If venue permission introspection is insufficient, fail activation until an independently documented verification step is available. Display REAL MONEY TRADING ENABLED persistently. Phase 1 has no LIVE capability.

## Secret and agent isolation

Use Docker secrets or owner-readable external secret files in production; environment variables are a development option. No secrets in source, build arguments, images, fixtures, URLs, traces or exception bodies. Encrypt stored provider/exchange credentials with an externally managed key and versioned envelope; restrict decryption to the process needing the secret. Key rotation must preserve decryptability of backups. Never mount the Docker socket or host root into application or research containers.

Research receives sanitized exports or read-only analytics views, separate metadata write access, a bounded workspace and no production trading credentials. Candidate code remains untrusted until review. It can create experiments/branches/PRs but cannot promote itself, edit live limits, access production executor endpoints, or mutate production balances. Provider text is data, never executable code or instructions to bypass policy. Research container network membership alone is not an authorization boundary; DB grants and secret isolation are mandatory.

**AI proposals (ADR-017, supersedes ADR-016)**: `apps/ai_worker` may use the operator's local
`claude`/`codex` CLI to analyze validated public market context, but it can only persist a
schema-validated, operator-scoped `TradeProposal`. It has no execution gateway, account balance,
order-building, withdrawal or transfer capability. An authenticated operator chooses approve,
reject or simulate. Only the MFA-protected API route, after committing that one-time approval,
may revalidate it against data freshness and the deterministic controls and submit one PAPER
order through the AI account's simulated gateway. ADR-018 additionally allows an explicitly
activated, operator-owned LIVE spot account, with per-order mode/policy binding and revalidation.
The worker may read only the sanitized cash/holding snapshot, not private credentials or execution
tables. The worker's local CLI access never
turns untrusted model text into an executable instruction.

Do not create an agent HTTP endpoint until needed. If introduced, require a narrowly scoped service identity and an HMAC over method, path, exact-body hash, timestamp and nonce. Store nonce consumption atomically with TTL, use constant-time signature comparison and a bounded timestamp window; reject if replay storage is unavailable. Rotate keys; consider mTLS for transport identity. Only the authorized WallyBot service may call it.

Telegram later uses allowlisted numeric user/chat IDs, replay-resistant expiring confirmation tokens and separate scopes. Sensitive commands require confirmation and a step-up web flow where appropriate. Notifications never contain secrets. Research automation cannot send unauthorized external messages.

## Hardening and auditing

Run containers as non-root with dropped capabilities, read-only root filesystems and explicit writable volumes. Pin image/dependency versions and scan in CI. Limit request/body sizes, timeouts and concurrency. Use parameterized DB access; allowlist provider endpoints to avoid SSRF. Restrict CORS to the single application origin, validate WebSocket origin/session and revoke live streams when sessions expire.

Audit login failures, MFA events, sessions, role/config/credential changes, live activation, promotions and emergency actions. Store actor, time, correlation ID, redacted before/after values and reason; audit protected state mutations in the same transaction. The runtime cannot update/delete audit rows. A separate export to protected backup storage provides tamper evidence beyond a compromised application; local DB permissions alone are not tamper-proof.

There is no withdrawal interface, route, background job or research tool. Reconciliation may observe external withdrawals, but autonomous code never initiates them. Dependency libraries may contain withdrawal APIs; production adapters do not expose or invoke those APIs. Test the public capability surface and scan for forbidden calls.

Incident response: persist EMERGENCY, revoke live lease, inspect and reconcile outstanding orders, rotate compromised credentials, invalidate sessions, preserve audit evidence, then require operator rearm. Do not equate a stopped process with cancelled exchange orders. See [deployment](DEPLOYMENT.md) for backup and origin controls.
