# Foundation security verification

Recorded 2026-09-11 (America/Mexico_City), using local Docker Desktop Linux images. These results describe the tested foundation, not a production security certification.

| Check | Result |
| --- | --- |
| Python dependency audit | pip-audit: no known vulnerabilities after upgrading cryptography to 50.0.1 |
| JavaScript dependency audit | Full pnpm audit, including development dependencies: no known vulnerabilities |
| Python static security checks | Bandit passed |
| Application runtime | Python 3.12.14 Alpine with vendor package updates: zero HIGH/CRITICAL findings |
| PostgreSQL runtime | PostgreSQL 17.11 Alpine with package updates and su-exec wrapper: zero HIGH/CRITICAL findings |
| Web and gateway runtimes | Nginx 1.30.4 Alpine, pinned base digest with package updates: zero HIGH/CRITICAL findings for both images |
| Redis runtime | Redis 7.4.11 Alpine: zero HIGH/CRITICAL findings |
| Runtime verification | All eight long-running services healthy; readiness endpoint passed |
| Recovery verification | Encrypted backup restored into fresh disposable PostgreSQL using the final custom image; foundation checks passed |

Container scans used Trivy 0.69.3 with current downloaded vulnerability data and no advisory suppressions. Scans above cover HIGH and CRITICAL severity; they do not claim absence of lower-severity findings or unknown vulnerabilities. Local JSON reports are generated in ignored `logs/`; the final PostgreSQL report is `postgres-final-scan.json`. The CI workflow blocks HIGH/CRITICAL findings for all five runtime images, but has not yet run remotely.

The Nginx base is pinned to `sha256:442753882674b49ae2c1de83ed67896131c0777f56df5005e356e62bc3f7e7ce`. PostgreSQL's obsolete statically linked Go helper was removed and replaced with a shell wrapper invoking Alpine's privilege-drop helper. Fresh initialization, restart and isolated restore succeeded. See [ADR-012](../adr/012-runtime-base.md) for the runtime decision.

Authentication, role isolation, CSRF, TOTP replay prevention and failure handling have automated coverage listed in [testing](testing.md). Production HTTPS, Fedora deployment, external origin filtering and off-host backup custody still require validation on the deployment host. Trading and financial controls have not been implemented or certified by these foundation checks.
