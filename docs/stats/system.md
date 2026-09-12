# System inventory

Foundation 0.1.0. Eight long-running services: gateway, web, API, PostgreSQL, Redis, worker, scheduler and research. A one-shot Alembic service applies revision `0001_foundation` before app startup.

Local verified host binding: `127.0.0.1:3333`. No standard-stack PostgreSQL/Redis host ports. Production template supports `0.0.0.0:3333` when explicitly configured; no Fedora/Cloudflare production instance has been deployed.

Worker and scheduler poll every five seconds. Heartbeat becomes stale after 30 seconds. Research has a four-GiB cap, one CPU and no authentication secrets or Redis credentials. It performs no research jobs yet.

This inventory is not a throughput or memory benchmark. Container caps are configured, not measured capacity guarantees. `/api/system` requires authentication and reports observed service health.
