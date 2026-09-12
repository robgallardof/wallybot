# ADR-009: One origin on port 3333

Status: accepted for design, 2026-09-09.

Context: one local/production application URL is required while databases stay private.

Decision: production gateway publishes `0.0.0.0:3333`; API, DB, Redis and workers publish no ports. Cloudflare reaches the gateway and origin access is restricted. Hybrid development explicitly publishes DB/cache only on loopback using a named dev override, with Vite serving/proxying on loopback 3333.

Alternatives: separate public service URLs fragment auth and exposure. Bare private Compose infrastructure is unreachable by host-run applications. A duplicate local gateway alongside Vite would contend for the same port.

Consequences: validate production and dev Compose separately. Tunnel-only loopback production binding can be an operator override; it is not silently substituted for the requested baseline.
