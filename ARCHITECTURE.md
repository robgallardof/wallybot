# WallyBot architecture

Status: design baseline with a Phase 1 foundation implemented on 2026-09-10. Authentication, controls, processes and deployment exist; quantitative, financial and exchange capabilities below remain planned. See [verification status](docs/stats/testing.md).

## Boundaries and deployment shape

Use a modular monolith with independently launched API, trading worker, scheduler, and research worker processes. Share typed domain and application packages; each process has a narrow composition root and separate credentials. Start with one trading worker per account. Research has separate resource limits and cannot invoke production execution.

Only the gateway publishes host port 3333. It routes `/api/*` and `/health/*` to FastAPI and remaining application routes to the web service. React owns navigation, including setup, login, dashboard, portfolio, markets, asset details, positions, orders, trades, decisions, AI, strategies, backtests, experiments, research, speculative radar, risk, events, logs, system, and settings. Phase 1 implements setup/login/dashboard/system; deferred pages explicitly indicate unavailable capabilities and never present invented financial results.

Use one frontend at `apps/web`; omit the proposed duplicate `frontend/` tree. Public URLs share one origin. PostgreSQL is authoritative; Redis accelerates data access and delivery. Parquet and DuckDB serve historical analysis. No cross-service financial transaction relies on Redis.

## Planned repository

```text
apps/{api,worker,scheduler,research_worker,web}/
wallybot/
  domain/          # values, entities, pure rules, ports
  application/     # use cases and transaction orchestration
  market/ data/ exchanges/ execution/ portfolio/ risk/
  strategies/ signals/ scoring/ ai/ research/ analytics/
  backtesting/ simulation/ events/ notifications/ security/
  infrastructure/ # DB, caches, transport, settings, telemetry
tests/{unit,integration,contract,property,e2e,fixtures}/
docs/{adr,diagrams,runbooks,stats}/
migrations/ scripts/ docker/ data/ logs/
pyproject.toml uv.lock docker-compose.yml docker-compose.dev.yml
Makefile .env.example README.md
```

Create modules when a real capability needs them; avoid empty placeholder classes. Runtime data and logs are ignored by version control. Domain code imports neither FastAPI, SQLAlchemy, CCXT nor AI SDKs. Capability packages implement domain ports; application use cases compose them. Composition roots supply adapters and settings. Controllers validate transport input and call use cases.

## Contracts

All identifiers are stable IDs; all timestamps are aware UTC; monetary values use decimal types. Transport schemas use Pydantic v2 with explicit bounds, schema versions, and forbidden unknown fields where input controls behavior. Domain models are independent of transport schemas.

| Port / value | Responsibility and restrictions |
| --- | --- |
| `Clock`, `IdGenerator` | Inject time and IDs for replay and deterministic tests |
| `MarketDataProvider` | Discover instruments, fetch candles/snapshots, stream normalized events; no trading credentials |
| `MarketMetadataProvider`, `TokenSafetyProvider` | Return timestamped provenance and unknown/missing fields explicitly |
| `FeatureEngine` | Versioned features from validated as-of data; no future observations |
| `Strategy.evaluate(context) -> StrategySignal` | Pure recommendation; cannot submit orders or mutate balances |
| `SignalAggregator` | Deterministic weighting, agreement and disagreement; HOLD on invalid quorum |
| `AIProvider.analyze(snapshot) -> AIRecommendation` | Structured advisory result and usage; no execution capability |
| `PortfolioAllocator` | Proposed allocation under bucket, asset and cluster capacities |
| `RiskEngine.evaluate(proposal, context) -> RiskAssessment` | Authoritative reject/approve/reduced size, reasons and input versions |
| `ExecutionService` | Load durable intent and approval, revalidate, reserve capacity, submit via gateway |
| `ExchangeGateway` | Capabilities, balances, order lookup/submission/cancellation and fills; no withdrawal method |
| `UnitOfWork`, repositories | Transactional writes, locking, unique constraints and outbox |
| `ResearchRunner` | Immutable dataset and code inputs, bounded resources, artifacts; no promotion authority |

Order intents contain account, mode, instrument, side, type, quantity, price constraints, decision ID, client order ID, idempotency key, expiry, risk assessment ID and configuration versions. Approval is persisted and bound to the exact intent digest and reservation; a caller-supplied `approved=true` has no meaning. Exchange adapters expose only supported order types and precision/minimum rules.

## Decision and execution flow

Collectors normalize data; quality checks gate features; universe filters reject unavailable, illiquid, wide-spread, insufficient-history or unsafe markets. Versioned scoring ranks finalists. Regime classification and strategies produce signals. Optional AI analyzes finalists under a budget. Allocation proposes size; risk has final veto. Rejections are persisted for counterfactual analysis as well as approvals.

Within an account-serialized transaction, read current state, evaluate risk, reserve cash/exposure, persist decision/assessment/intent and outbox event. Before external submission, verify current mode, configuration, approval expiry, data freshness, exchange health and reservation. Stale decisions go through risk again. Do not hold a database transaction open during network requests.

An executor claims intents durably and records SUBMITTING before the network call. An ambiguous result becomes UNKNOWN; order lookup and reconciliation resolve it before any retry. A gateway without reliable client ID reconciliation cannot qualify for LIVE. Database uniqueness provides internal deduplication, not magical exactly-once external execution. See [DATA](DATA.md) and [order lifecycle](docs/diagrams/order-lifecycle.md).

Fills commit with balanced ledger postings, position projection changes and outbox events in one transaction. Async consumers may retry; an inbox unique event ID prevents duplicate side effects. Notifications and analytics can lag without invalidating financial truth.

## Modes and capability gates

PAPER is the fresh-install default. OBSERVER analyzes without intents; PAPER uses an exchange simulator; LIVE requires the separate activation gate; PAUSED blocks increasing exposure; EMERGENCY blocks normal execution and invokes its separately configured policy. Store environment (paper/live account) independently from operational status, so pausing does not change the ledger or switch the exchange. Never send paper intents to live adapters.

Persist pauses, emergency state and risk changes across restarts. A restart revokes the live execution lease and requires reconciliation plus operator rearm before LIVE resumes. Existing exchange orders may still fill while the process is down; recovery always reconciles them.

## Technology decisions

Adopt Python 3.12+, uv, FastAPI, Pydantic v2/Settings, SQLAlchemy 2, Alembic, asyncio and httpx. Frontend uses React, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query/Table, Zod and React Hook Form. Plan Lightweight Charts for candles and Recharts for portfolio charts. Pin exact dependency versions and lockfiles during Phase 1 after compatibility tests; this document does not assert current latest versions.

Quantitative dependencies enter the research extra: NumPy, Pandas, Polars, SciPy, scikit-learn and statsmodels. Begin with transparent vectorized indicators, compare them with reference fixtures, and evaluate TA-Lib/pandas-ta for correctness, supported Python versions, licensing and installation cost before adoption. ML, optimization and sentiment remain later experiments.

Use CCXT behind REST/execution ports. Evaluate native Kraken WebSocket against CCXT Pro for reconnect recovery, sequence gaps, timestamps, subscription limits, maintenance and licensing in Phase 2. Prefer the implementation that passes fault tests; do not declare reliability without evidence. Binance and Coinbase are later adapters. Market-only derivatives data does not enable derivatives execution.

## Scheduling, events and observability

PostgreSQL stores jobs with a unique `(job_type, scheduled_for, scope)` and durable status. Workers claim with database locking and leases; expired leases permit bounded retry, with idempotent handlers. Redis wakes workers and caches results; periodic DB scans recover lost notifications. Research has a separate queue and concurrency one initially.

Emit versioned events with correlation/causation IDs. Structured logs include timestamp, level, service, correlation ID, decision ID, exchange, symbol, event and message; inapplicable fields are null. Redact at source. Prometheus labels exclude unbounded IDs; logs/traces carry those IDs instead. Track queue lag, stale data, unknown orders, reconciliation age, risk vetoes, latency, errors and AI costs. OpenTelemetry spans follow the decision path. UI health must distinguish operational, degraded, unavailable and not configured.

## Implementation sequence

| Phase | Deliverable and exit boundary |
| --- | --- |
| First design phase | These six documents, ADRs and diagrams; no application build |
| 1 | Authenticated foundation and Docker acceptance; [backlog](docs/PHASE_1.md) |
| 2 | Fake/Kraken market discovery, data quality, streaming, features and scanner |
| 3 | Scoring, regimes, strategies, allocation and tested deterministic risk |
| 4 | Replay, paper execution, ledger and recovery under failures |
| 5 | Immutable datasets, backtests, walk-forward, Monte Carlo, benchmarks |
| 6 | Provider-neutral AI, strict decisions, calibration and cost accounting |
| 7 | Isolated research agent workflows, experiments and reports |
| 8 | Authorized Telegram commands and severity-based reporting |
| 9 | Human-approved, small-capital Kraken LIVE only after evidence gates |
| 10 | More venues/providers, speculative research, news, ML and robust optimization |

Each feature needs typing, validation, tests, error behavior, telemetry and documentation. No phase silently promotes a strategy or grants autonomous withdrawals. See [architecture diagram](docs/diagrams/architecture.md).
