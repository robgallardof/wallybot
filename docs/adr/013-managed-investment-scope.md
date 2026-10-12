# ADR-013: Managed investment scope and no-withdrawal boundary

Status: accepted for design, 2026-09-16.

## Context

WallyBot is intended to manage an operator-funded investment mandate (for example, USD 10,000),
not merely to display analytics. The mandate may cover supported crypto assets (BTC, ETH and
eligible higher-risk tokens) and broker-supported securities such as ETFs. The system needs to
combine market, portfolio, wallet and intelligence context periodically, decide whether to buy,
hold, reduce or sell, and explain when an operator should move funds out of a venue.

The distinction between selling an asset and withdrawing funds must remain explicit. A sale can
move a managed position into the account's configured cash/settlement asset. A withdrawal moves
funds outside that account and is a separate, high-risk transfer capability.

## Decision

- The operator supplies an explicit account-scoped investment mandate: funding amount, permitted
  venues and asset classes, allocation/risk limits, execution mode and a review cadence. Amounts,
  valuations and costs use Decimal and immutable snapshots.
- Read-only exchange/broker and wallet adapters provide balances, positions, fills, transfers and
  observed on-chain activity. No private key, seed phrase or withdrawal permission is accepted by
  WallyBot.
- A periodic context assembler records the as-of portfolio valuation, open positions/reservations,
  realized/unrealized performance, prior decisions and outcomes, market quality, token safety,
  wallet/entity signals and provider reliability. The AI receives this typed, timestamped,
  provenance-preserving context only.
- The AI may emit a schema-validated BUY/LONG, HOLD, or SELL/REDUCE `TradeProposal`; it may also
  emit a non-binding `withdrawal_recommendation` for the operator. It has no order, transfer,
  credential or policy-mutation tool.
- A proposal passes `PortfolioAllocator` and `RiskEngine`, then runs in OBSERVE/SHADOW/PAPER by
  default. LIVE order submission requires the existing explicit activation, reconciliation,
  trade-only venue credential and human approval gates. A buy/sell action is never inferred from
  confidence alone.
- Exchange and broker adapters expose balances, orders, fills, cancellations and reconciliation
  only. They do not expose withdrawal, transfer, address-book or private-key methods. A withdrawal
  recommendation is displayed/audited and must be performed by the operator outside WallyBot.
- Crypto assets and ETFs share portfolio/risk accounting but use different adapter capabilities,
  market-hours calendars, settlement and liquidity rules. Unsupported instruments fail closed.

## Consequences

WallyBot can grow, hold, reduce and liquidate an approved managed portfolio while keeping a
verifiable, reproducible rationale for every decision. It can tell the operator when to withdraw
or de-risk, but cannot move funds outside the managed venue even if compromised. Provider keys are
trade-only and withdrawals must be disabled at the venue before any LIVE eligibility.

Implementation follows this order: mandate + portfolio context snapshots; read-only wallet/broker
adapters; AI costed advisory and periodic SHADOW; PAPER execution/evaluation; then separately
reviewed LIVE trading. Backtests and SHADOW evidence are required before promotion; no strategy
is promoted solely because of retrospective profit.

**Partially superseded by [ADR-016](016-ai-autonomous-account.md) (2026-09-23)** for one narrow,
named exception: a separate, opt-in AI-autonomous PAPER account may skip the "passes
`PortfolioAllocator` and `RiskEngine`" step in this ADR's Decision section — confirmed twice by the
operator after concrete failure scenarios were raised. The no-withdrawal boundary and PAPER/LIVE
gating this ADR describes are unaffected and still fully apply.
