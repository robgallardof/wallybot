# ADR-014: Multi-provider investment platform, token management and copy-signal controls

Status: accepted for design, 2026-09-16.

## Context

Users may hold crypto, cash and securities across different exchanges, brokers and read-only
wallets. They need one WallyBot interface for live market data, charts, token research, holdings,
orders, decisions, portfolio history, risk, research and provider health. A provider must be
replaceable: adding Binance, Bitso, Kraken, Coinbase or a securities broker cannot change the
portfolio/risk/AI contract or expose one provider's credential to another.

Copy trading is a signal source, not a safe execution shortcut. A public wallet, trader or
provider strategy can be incomplete, delayed, manipulated, unverified or incompatible with an
operator's portfolio constraints.

## Decision

### Connection model

- Introduce a versioned provider registry. Each connector declares its asset classes, regions,
  market-data capabilities, trading capabilities, supported order types, rate limits, precision,
  trading calendar, read-only/trade-only credential requirements and health state.
- Connections are account-scoped and begin in `READ_ONLY`. Wallet connections use public address
  or an explicitly read-only API scope. Exchange/broker connections may advance to `PAPER` and,
  separately, `TRADE_ONLY` only after credential validation proves that withdrawals, transfers and
  address-book changes are disabled.
- Credentials are encrypted, separately scoped per provider/account and decrypted only by the
  adapter process that needs them. The web client never receives a secret after submission.
- Market data, charts and provider telemetry are normalized into timestamped candles, snapshots,
  order books and quality/reliability records. A chart always identifies source, freshness and
  whether it is a consensus view; stale data cannot authorize an order.

### Product surfaces

The single React application will provide compatible pages for Connections, Portfolio, Markets and
Charts, Tokens, Wallets, Orders/Fills, Decisions/AI, Copy Signals, Strategies, Backtests,
Experiments/Research, Risk, Activity and System. An unavailable capability is shown explicitly;
the UI never invents balances, positions, performance or real-time data.

The Token Manager maintains token identity, chain/contract, venue listings, metadata, safety
assessment, liquidity, holder concentration, provider provenance and watchlist/eligibility state.
It gates speculative assets before strategy/AI/risk evaluation and does not treat an exchange
symbol as a globally unique token identity.

### AI and copy signals

- Periodic AI context merges approved account balances/positions, observed wallet activity,
  market and token quality, provider health, historical decisions, fills and performance. Each
  input retains as-of time, source and version; missing/stale context produces HOLD.
- Copy sources have an explicit mode: `OBSERVE`, `AI_EVALUATED`, `SHADOW`, `PAPER` or `LIVE`.
  `MIRROR` is not an execution mode. A copy event becomes an attributable signal, then follows
  allocation, token safety and deterministic risk like any other proposal.
- Per-source allocation ceiling, maximum latency, independence/confidence threshold and cooldown
  are mandatory. A copied trade never bypasses an account mandate, concentration limit, liquidity
  gate or human LIVE approval.

## Consequences

Provider onboarding is incremental and contract-tested. Initial adapters prioritize public/read-
only market data and wallets; trade-only adapters require a separate security, reconciliation and
failure-recovery review. The dashboard can aggregate many providers without merging credentials
or assuming all tokens/markets are equivalent. WallyBot can execute approved buy/sell activity
within a funded account, but never transfer or withdraw money/coins from it.
