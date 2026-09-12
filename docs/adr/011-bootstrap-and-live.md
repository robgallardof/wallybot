# ADR-011: Protected bootstrap and explicit LIVE rearm

Status: accepted for design, 2026-09-09.

Context: an exposed first-boot endpoint can be claimed remotely, and restart must not unexpectedly resume real trading.

Decision: one-use out-of-band bootstrap token, atomic admin/TOTP activation, permanent setup disablement. PAPER on fresh install; persist operational stops and revoke LIVE lease on restart until reconciliation and operator rearm.

Alternatives: public first-user-wins setup risks takeover; persisting automatic live resumption can trade during incomplete recovery.

Consequences: operators need secure bootstrap/recovery procedures. Existing exchange orders still require reconciliation after restart. App authentication remains mandatory behind Zero Trust.
