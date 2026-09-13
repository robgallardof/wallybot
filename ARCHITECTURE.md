# WallyBot architecture

Status: design baseline with a Phase 1 foundation implemented on 2026-09-10, refactored on 2026-09-12 for explicit DTOs and single-responsibility layering (frontend and backend) without changing behavior. Authentication, controls, processes and deployment exist; quantitative, financial and exchange capabilities below remain planned. See [verification status](docs/stats/testing.md).

Scope expanded on 2026-09-13 into a multi-source financial intelligence, portfolio analysis and controlled trading platform: wallet/entity intelligence, Smart Money scoring, on-chain/whale/disclosure signals and an AI strategy layer producing `TradeProposal`s, all upstream of the deterministic risk/portfolio/execution pipeline that already exists. This is a target-architecture expansion, not a claim that any of it is implemented — see "Multi-source intelligence and Smart Money" and "AI strategy layer and TradeProposal" below for the design, and the implementation sequence for what is actually built (Phases 2-4: market data, signals/risk, PAPER execution/ledger).

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

All identifiers are stable IDs; all timestamps are aware UTC; monetary values use decimal types. Transport schemas use Pydantic v2 with explicit bounds, schema versions, and forbidden unknown fields where input controls behavior. Domain models are independent of transport schemas. API responses are explicit Pydantic output DTOs (`apps/api/dto.py`), declared via `response_model`, kept separate from request input schemas (`apps/api/schemas.py`) since input and output validation change for different reasons.

| Port / value | Responsibility and restrictions |
| --- | --- |
| `Clock`, `IdGenerator` | Inject time and IDs for replay and deterministic tests |
| `MarketDataProvider` | Discover instruments, fetch candles/snapshots, stream normalized events; no trading credentials |
| `MarketMetadataProvider`, `TokenSafetyProvider` | Return timestamped provenance and unknown/missing fields explicitly |
| `WalletIntelligenceProvider`, `EntityIntelligenceProvider`, `SmartMoneyProvider`, `OnChainAnalyticsProvider`, `BlockchainProvider` | Normalize wallet/entity/on-chain data into Wally domain objects; every claim keeps source, confidence, timestamp and evidence, never asserted as fact |
| `NewsProvider`, `MacroProvider`, `SocialSignalProvider`, `PoliticalDisclosureProvider`, `InstitutionalFlowProvider` | Timestamped, source-attributed external signals, same provenance rule as above |
| `SecurityAnalysisProvider` | Token/contract safety checks (mint/freeze authority, liquidity locks, honeypot indicators) feeding `TokenRiskScore` |
| `BrokerProvider` | Non-crypto broker abstraction under the same no-withdrawal-capability rule as `ExchangeGateway` |
| `FeatureEngine` | Versioned features from validated as-of data; no future observations |
| `Strategy.evaluate(context) -> StrategySignal` | Pure recommendation; cannot submit orders or mutate balances |
| `SignalAggregator` | Deterministic weighting, agreement and disagreement; HOLD on invalid quorum |
| `AIProvider.analyze(context) -> TradeProposal` | Structured, schema-validated advisory result; the AI's only output artifact; no execution capability |
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

## Multi-source intelligence and Smart Money

WallyBot's data sources extend beyond price/candle feeds: wallet activity, on-chain events, whale flows, political/corporate disclosures, news and macro data all normalize into the same event-sourced pipeline market data already uses (see Contracts). Every external claim keeps its source, confidence, timestamp and evidence — an attribution is never treated as ground truth, only as one provider's claim with a verification status.

An **Entity Registry** tracks real-world actors (person, public figure, politician, fund, company, exchange, institution, whale, trader, developer, market maker, protocol, ETF, government, wallet cluster, or an operator-defined custom type) with confidence/trust/risk/influence scores and full source provenance. A **Wallet Registry** tracks addresses (one entity may own several wallets, and wallets may cluster) with per-wallet monitoring mode, copy mode, influence weight and allocation ceilings — administered, never auto-escalated: a tracked wallet's activity becomes one signal among many (`AI_EVALUATED`), never an automatic trade duplication (`MIRROR` stays disabled by default). An **Entity Correlation Graph** stores typed relationships (owns, controls, funds, traded, transferred, deployed, holds, invested_in, disclosed_trade, insider_of, ...) between wallets, entities, tokens and events, each with its own provenance; the existing relational schema models this initially, a graph database is a later option if query patterns actually need one.

A **Smart Money Engine** scores wallets 0-100 from realized/unrealized PnL, win rate, profit factor, drawdown, a Sharpe-like risk-adjusted measure, trade count, wallet age, holding duration, consistency across market regimes, and rug/wash-trading exposure — never from a single profitable trade. Score snapshots are append-only history, never overwritten. **Smart Money clustering** detects independent tracked wallets converging on the same asset within a configurable window and emits a `SmartMoneyClusterSignal` with wallet count/identities/scores, an independence score (wallets controlled by the same entity never count as independent confirmations), liquidity/volume/holder deltas and confidence.

**Token intelligence** (market cap, FDV, liquidity, holder concentration, contract/pool/developer-wallet age, mint/freeze authority, liquidity locks, honeypot indicators, buy/sell tax, known malicious labels) produces a `TokenRiskScore` gating any speculative proposal before risk evaluation. **Whale intelligence** tracks large transfers and exchange/stablecoin flows as signals, not as an automatic BUY/SELL interpretation — the strategy/AI layer interprets them in context. **Political and financial disclosure** ingestion (congressional trades, SEC Form 4, 13F, corporate lobbying, dark-pool activity) stores both transaction date and disclosure date and computes a `DisclosureLag`; a large lag reduces real-time trading relevance without discarding the data's backtesting value. **On-chain monitoring** prefers event/webhook subscriptions over polling and normalizes buy/sell/swap/transfer/mint/burn/liquidity/stake/bridge activity with source and destination wallet, token, pool, DEX, price, gas, slippage and liquidity.

Every one of these becomes a normalized **signal**: a score in [-100, 100], a confidence in [0, 1], a TTL, a source and an as-of timestamp, combined through a configurable, backtestable weighted ensemble per strategy — weights are never permanently hard-coded. Signals **decay**: the engine tracks event time separately from observation time, and a real-time wallet event, a breaking market event, an SEC filing and a 13F all decay on different, configured timescales. **Provider reliability** (latency, errors, rate limits, freshness, outages, cross-provider disagreement) drives circuit breakers and exponential backoff with jitter; no single provider is ever the sole source of truth for a decision that can move money, and where multiple independent price feeds exist WallyBot computes a consensus price and rejects orders against a stale or outlier quote.

Public-figure monitoring (politicians, public investors, fund managers, known traders, companies, ETFs, market makers) uses only legally obtained public information and public blockchain data, and never attempts to deanonymize private individuals. Crypto activity and securities disclosures are separate signal types and are never merged into one claim.

## AI strategy layer and TradeProposal

The fundamental rule does not change with this expanded scope: an AI model is an analyst and strategy generator, never an executor. Its only output is a schema-validated `TradeProposal` (asset, market, direction, strategy, confidence, suggested allocation/entry/stop/take-profit, time horizon, signal TTL, reasons, risks, supporting signals, invalidating conditions, source event IDs, model ID and prompt version) — the same restriction the Contracts table's `AIProvider.analyze(context) -> TradeProposal` already names, with a richer, more auditable contract than a bare recommendation. Invalid or malformed model output fails closed: it cannot become an executable recommendation, and AI-required strategies HOLD when AI is unavailable, exactly as RISK.md already requires.

The full pipeline, in order: data sources → event ingestion → normalization → intelligence (entities, wallets, smart money, tokens, disclosures) → feature engineering → the AI/strategy engine → `TradeProposal` → `RiskEngine` → portfolio policy → `PortfolioAllocator` → `ExecutionService` → `ExchangeGateway`/broker. This is the same flow "Decision and execution flow" above already describes (quality gate → universe filter → scoring → regime/strategy signals → optional AI → allocation → risk veto), with the AI's output formalized as `TradeProposal` and intelligence sources added upstream of feature engineering — not a competing or parallel pipeline. `RiskEngine` keeps final veto exactly as built: AI cannot override a REJECTED decision, and a REJECTED assessment cannot execute regardless of confidence.

AI tools are narrowly scoped, typed, read-only functions — for example `get_market_snapshot`, `get_wallet_activity`, `get_entity_activity`, `get_smart_money_signals`, `get_token_security`, `get_portfolio_state`, `get_strategy_performance`, `create_trade_proposal`. No tool may submit an order, withdraw, transfer funds, change risk policy, or read a private key or exchange secret. SECURITY.md's "Secret and agent isolation" section is authoritative on this boundary and needs its own follow-up update enumerating this exact allow/deny list once these tools are built — that update is not made here.

Every `TradeProposal` and its resulting `RiskAssessment`/`OrderIntent` must be as auditable as an approved one: what signals fired, what the AI concluded and from what evidence, what confidence and risks were assigned, what the risk engine did and why, and what happened afterward. Storing only the final decision is not sufficient — the evidence is part of the record, extending this document's existing "Rejections are persisted for counterfactual analysis as well as approvals."

## Portfolio policy buckets

Buckets are configurable allocation policy, not a promise about investment safety (RISK.md). The implemented default is Core/Growth/Speculative 70/20/10 (`wallybot/domain/portfolio.py`'s `Bucket` enum; RISK.md's Initial Policy table); this expanded vision's own vocabulary says Core/Tactical/Speculative at the same percentages. Renaming `GROWTH` to `TACTICAL` is a real, tracked reconciliation item — it touches shipped domain code plus RISK.md and tests — not something done silently as part of a documentation update. Administrators may change bucket targets. Beyond the maximum/minimum allocation and speculative ceilings already implemented (RISK.md), each bucket is planned to eventually carry its own maximum position size, maximum correlated exposure, maximum daily loss, maximum drawdown, maximum position count, allowed strategies/asset classes/exchanges, minimum liquidity, maximum slippage, minimum confidence/risk score, cooldown and execution mode; none of these per-bucket fields are modeled yet. Speculative allocations additionally need tighter, separately configured limits for new tokens, memecoins, low-liquidity assets, unverified tokens, wallet-copy signals and newly deployed contracts, gated by `TokenRiskScore` before risk evaluation.

## Modes and capability gates

PAPER is the fresh-install default. OBSERVER analyzes without intents; PAPER uses an exchange simulator; LIVE requires the separate activation gate; PAUSED blocks increasing exposure; EMERGENCY blocks normal execution and invokes its separately configured policy. Store environment (paper/live account) independently from operational status, so pausing does not change the ledger or switch the exchange. Never send paper intents to live adapters.

Persist pauses, emergency state and risk changes across restarts. A restart revokes the live execution lease and requires reconciliation plus operator rearm before LIVE resumes. Existing exchange orders may still fill while the process is down; recovery always reconciles them.

Independently of the account-level environment above, every strategy and every tracked wallet/entity carries its own execution mode: OBSERVE (collect data only), PAPER (simulate the full trade), SHADOW (generate real `TradeProposal`s and compare them against real market outcomes without ever submitting an order) or LIVE (execute only after every deterministic policy passes). These are orthogonal to the PAPER/LIVE account environment — a strategy can run SHADOW against a PAPER account, or stay in OBSERVE indefinitely. Every newly created strategy or newly tracked wallet/entity defaults to OBSERVE.

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
| 10 | Wallet/entity intelligence infrastructure — Entity/Wallet Registry, correlation graph, on-chain event ingestion; OBSERVE mode only, no execution authority, buildable in parallel with earlier phases |
| 11 | Smart Money scoring and clustering, token/whale intelligence, provider reliability and price consensus |
| 12 | AI strategy engine producing schema-validated `TradeProposal`s, wired into the existing `RiskEngine`/`PortfolioAllocator`/`ExecutionService` pipeline; SHADOW mode before any LIVE eligibility |
| 13 | Political/corporate disclosure engine (congressional trades, Form 4, 13F), public figure monitoring |
| 14 | Admin UI for entities, wallets, Smart Money, signals, trade proposals and decision explainability |
| 15 | Additional venues/providers, broader speculative research, robust optimization |

Each feature needs typing, validation, tests, error behavior, telemetry and documentation. No phase silently promotes a strategy or grants autonomous withdrawals. See [architecture diagram](docs/diagrams/architecture.md).
