"""Prometheus metric objects shared across `apps/api`'s background loops and routes.

`docs/PENDING.md`'s "Observabilidad" row asks for metrics on "datos, colas, riesgo, UNKNOWN,
conciliación, costes y recursos". Covered here: data ingestion/price-consensus tick outcomes,
the research job queue depth, active breakers, reconciliation health and UNKNOWN orders. Not
covered, on purpose: process resource usage (CPU/memory/GC/fds) is already exported for free by
`prometheus_client`'s default collectors registered on import, nothing to add here. "Costes"
(AI/provider spend) has no real source yet -- Fase 6's AI provider is still a stub -- so no cost
metric exists; adding one now would be a fabricated number with nothing behind it.

Every label here is a small, fixed set (a handful of literal strings or the 4-member
`BreakerType`), never an unbounded identifier (`account_id`, `experiment_id`, `client_order_id`)
-- PENDING.md's own "etiquetas sin IDs ilimitados" rule, and the standard Prometheus cardinality
guidance this codebase already follows for `wallybot_http_requests_total`'s `status_class` label.
"""

from prometheus_client import Counter, Gauge, Histogram

DECISION_TICKS = Counter(
    "wallybot_decision_tick_total", "Decision loop ticks by outcome", ["result"]
)
DECISION_TICK_DURATION = Histogram(
    "wallybot_decision_tick_duration_seconds", "Decision loop tick duration"
)
ORDERS_PLACED = Counter("wallybot_orders_placed_total", "PAPER orders placed by the decision loop")
ACTIVE_BREAKERS = Gauge(
    "wallybot_active_breakers", "Currently active circuit breakers, by type", ["breaker_type"]
)
RECONCILIATION_HEALTHY = Gauge(
    "wallybot_reconciliation_healthy", "1 if the last reconciliation sweep found no errors, else 0"
)
RECONCILIATION_UNKNOWN_ORDERS = Gauge(
    "wallybot_reconciliation_unknown_orders",
    "Open orders the last reconciliation sweep left UNKNOWN",
)
RESEARCH_JOBS_ACTIVE = Gauge(
    "wallybot_research_jobs_active", "PENDING or RUNNING research jobs right now"
)
PRICE_CONSENSUS_TICKS = Counter(
    "wallybot_price_consensus_tick_total", "Price consensus loop ticks by outcome", ["result"]
)
MARKET_INGESTION_TICKS = Counter(
    "wallybot_market_ingestion_tick_total",
    "Market data ingestion loop ticks by outcome",
    ["result"],
)
TELEGRAM_COMMAND_TICKS = Counter(
    "wallybot_telegram_command_tick_total", "Telegram command poll ticks by outcome", ["result"]
)
SERVICE_HEARTBEAT_AGE = Gauge(
    "wallybot_service_heartbeat_age_seconds",
    "Seconds since each background service's last heartbeat",
    ["service"],
)
