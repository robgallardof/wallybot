# Data and financial consistency

Status: Phase 1 identity, sessions, controls, audit events, heartbeats and maintenance jobs are implemented in migration `0001_foundation`. Financial, historical and research schemas below remain planned. There is no ledger or trading dataset yet.

## Three storage tiers

| Tier | Store | Contents | Failure semantics |
| --- | --- | --- | --- |
| Hot | Redis | Latest validated snapshots, ephemeral rankings, cache, wakeups | Rebuildable; missing/stale values prevent risk-increasing execution |
| Operational | PostgreSQL | Users, sessions, settings, decisions, orders, fills, ledger, jobs, events, strategy/research metadata | Authoritative; unavailable DB blocks submission and mutations |
| Historical | Immutable Parquet + DuckDB | Partitioned candles/trades/features and experiment datasets | Manifested, checksummed, versioned; never silently rewrite a research input |

Redis locks are efficiency aids, not financial exclusion. Account locks, reservations, deduplication and job truth live in PostgreSQL. Maintain separate DB users and grants for migrations, API, trading, scheduling and research. Research reads approved views/exports and writes only its own experiment metadata.

## Operational schema plan

| Group | Main tables and constraints |
| --- | --- |
| Identity | users (normalized login unique), MFA credentials (encrypted), hashed sessions/recovery codes, bootstrap singleton |
| Control | configuration_versions, mode_state, live_execution_leases, strategy_versions, promotions; immutable history and actor |
| Instruments | venues, accounts, instruments, instrument_rules; unique venue/instrument identifier and dated precision rules |
| Decisions | market_snapshot_refs, feature_versions, decisions, signals, ai_calls, risk_assessments; immutable input/version linkage |
| Execution | order_intents, reservations, orders, order_transitions, fills; scoped idempotency and fill uniqueness |
| Accounting | ledger_accounts, ledger_transactions, ledger_postings, position_lots, portfolio_snapshots, reconciliations |
| Delivery | events, outbox, consumer_inbox, scheduled_jobs, job_attempts, service_heartbeats |
| Research | dataset_manifests, experiments, backtest_runs, artifacts, benchmark_runs, outcome_evaluations |

Every financial row carries account and PAPER/LIVE environment. Foreign keys and composite consistency constraints prevent cross-account or cross-environment links. Instrument identity includes venue, market type, base and quote; do not assume all assets are crypto or use an ambiguous symbol as primary key.

Use `NUMERIC`/Python Decimal for money, price, fees and quantities; define field precision from supported venue capabilities and reject overflow rather than truncate. Float arrays are allowed in research/features, never authoritative money. Record native fee currency and conversion rate/source/time separately. Store aware `timestamptz`, distinguish exchange time, received time, processed time and candle close time. API decimals are strings; clients must not round amounts used in commands.

## Atomicity and deduplication

Lock the account control/reservation row in a consistent order for risk approval and exposure reservation. All approval paths use this lock, including manual orders. This prevents two individually valid approvals from exceeding aggregate capacity. Each approved intent reserves worst-case cash and exposure including fee/slippage allowance. Open orders and partial fills remain part of capacity calculations.

Unique `(account_id, environment, idempotency_key)` identifies an intent; replay with the same payload returns the original result, while a different payload conflicts. Client order IDs are deterministic within venue restrictions and mapped durably before submission. Uniqueness also covers `(venue, account_id, environment, exchange_fill_id)`; when a venue lacks stable fill IDs, define and contract-test a conservative reconciliation key before LIVE support.

Persist SUBMITTING and attempt identity before calling an exchange. A crash after submission may leave SUBMITTING even when the exchange accepted; recovery treats it as ambiguous. UNKNOWN retains reservations until reconciled. Retry a network submission only after authoritative absence and venue guarantees establish safety; otherwise pause for manual resolution. Cancellation requests are not evidence of cancellation, and fills racing cancellation must still post.

On a new fill, a transaction inserts the deduplicated fill, balanced postings, position updates, remaining reservation and outbox event. Ledger postings are immutable; corrections use reversing transactions. Enforce debit/credit equality per asset/currency within a journal transaction at commit, not just through application conventions. A BTC/USD trade records balanced BTC entries and balanced USD entries with clearing accounts; it never adds BTC units to USD units. Negative inventory/cash constraints respect only explicitly modeled liabilities; initial spot mode permits no borrowing.

Use a documented FIFO lot convention initially for realized PnL, independent from tax-jurisdiction treatment. Unrealized PnL references a timestamped valuation; unknown prices yield incomplete valuation and block additional risk. Positions are rebuildable projections of fills/ledger, not a replacement for history. Mark external deposits/withdrawals as observed account movements; this is reconciliation data, never an autonomous withdrawal capability.

A transactional outbox provides at-least-once delivery. Each consumer inserts its event receipt and effects atomically when both live in PostgreSQL. External notifications have deduplication keys and may still have ambiguous delivery; they do not influence financial truth.

## Reconciliation

Run at startup, before LIVE activation, periodically, after ambiguous requests, and after reconnects. Fetch overlapping windows of exchange orders/fills/balances, paginate to completion, deduplicate and record cursor/coverage. Compare open orders, cumulative fills, positions and balances using instrument precision and explicit tolerances. Do not treat a partial/failed fetch as an empty account.

Persist discrepancies and evidence; block new exposure for unknown orders, unexplained balances, stale reconciliation or incomplete coverage. Recover missing fills transactionally. Never silently overwrite the ledger with exchange balances. An operator can approve a documented correction after investigation. Reconciliation is account-scoped, serialized with financial updates, and restartable.

## Market quality and historical data

Normalized candles include venue, instrument, timeframe, open/close time, OHLCV, source and receipt time. Validate finite positive prices, nonnegative volume, low <= open/close <= high, timestamp alignment, duplicates, ordering, gaps, clock drift, stale age and abnormal returns. Validate books for positive levels, sorted sides, crossed markets and sequence continuity. A reconnect requires a fresh snapshot and resynchronization before healthy status.

Quality results are PASS/WARNING/FAILURE with reason codes and original evidence. Required-field gaps, staleness or failed synchronization are blocking. A warning is usable only when the explicit quality policy allows that reason. Never forward-fill a missing tradable price and label it fresh. Universe minimum history/liquidity and spread limits are versioned configuration.

Write partitions such as `data/market/kraken/BTC_USD/1m/date=2026-09-09/part-<id>.parquet`. Finalize via temporary file, checksum and atomic publication. A manifest records schema, source, acquisition window, row counts, quality flags and file hashes. Corrections publish a new version with lineage. DuckDB research reads an immutable manifest and bounded resources. Backtests use information available at decision time, include delisted assets where available, and disclose survivorship gaps.

## Analytics and retention

Separate trading fees, modeled slippage, AI cost, provider cost and infrastructure cost. Net returns calculated from actual fill prices already include execution price impact: do not subtract measured slippage twice. Show slippage as attribution against the decision benchmark. Track cash-flow-adjusted returns so deposits are not profit; align BTC, ETH, cash and BTC/ETH benchmarks to the same time window and cost assumptions.

Each experiment stores hypothesis, code hash, configuration, dataset manifest, seed, dependency lock hash, split boundaries, fill model, metrics and conclusions. Confidence intervals and walk-forward results must disclose sample size and selection procedure. Counterfactual evaluations use fixed predeclared horizons (15m, 1h, 4h, 24h) and are labeled hypothetical.

Initial proposed retention: hot values expire according to feed cadence; application logs 30 days; high-resolution nonfinancial telemetry 14 days. Financial/audit/strategy lineage has no automatic deletion until an operator defines retention requirements. Quarantine has bounded disk quotas. Backups include DB, protected settings and irreproducible research datasets. Monitor disk watermarks and stop new risk before persistence fails.

Alembic is the only schema migration path. Run one migration job before services become ready; use expand/migrate/contract changes for compatibility and back up before destructive migrations. Validate concurrency against real PostgreSQL, not SQLite. See [data flow](docs/diagrams/data-flow.md).
