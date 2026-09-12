# ADR-012: Updated Alpine runtime for the foundation

Status: accepted, 2026-09-10; validate the resulting image with Trivy and Docker health checks.

Context: the initial Python Debian slim image reported high-severity operating-system advisories without available vendor fixes. The matching Python Alpine image had seven libuuid advisories with packaged fixes.

Decision: use Python 3.12.14 Alpine for build and runtime, apply available package updates during image construction, and keep a blocking HIGH/CRITICAL scan in CI. Keep dependency lockfiles and record built image digests for releases. Do not suppress advisories to obtain a green result.

Tradeoff: Alpine uses musl. Phase 1 dependencies must install and run in the actual image; later numerical/research libraries may justify a separate glibc research image when their wheel support requires it. Reassess based on installation and quantitative test evidence.

Consequences: application image rebuilds receive OS security fixes and need regression tests. An exact Python tag plus package updates does not make future rebuilds byte-identical; promote the tested image digest, not an untested rebuild.

The PostgreSQL and Nginx images also apply vendor package updates. PostgreSQL replaces upstream's statically linked Go `gosu` helper with Alpine's `su-exec`, preserving the entrypoint's `gosu postgres ...` privilege-drop invocation through a small shell wrapper. This removes an outdated embedded Go runtime rather than suppressing its advisories. Fresh-volume initialization and normal restart must pass before promotion. Redis uses the corrected 7.4.11 image.
