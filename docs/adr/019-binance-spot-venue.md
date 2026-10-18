# ADR-019: Binance spot as the default venue

Status: accepted, 2026-10-12. Extends ADR-018; its approval, isolation and risk rules are unchanged.

The operator selected Binance as the default exchange.

## Decision

Real-account logic stays in `LiveTradingService`; exchange facts move behind a narrow
`LiveVenue` port (`wallybot/application/live_venues.py`): key verification, balances, open
orders, minimum notional, fee rate, visible book and an order gateway. Kraken and Binance
implement it. No venue exposes transfer, withdrawal or margin operations.

Binance specifics:

- Spot only, BTC/USDT and ETH/USDT. USDT is the account's cash currency; limits are entered in
  USDT. Any other non-zero asset, including BNB, blocks activation and trading.
- The key must report reading and spot trading only, with an IP restriction. Withdrawals,
  internal/universal transfer, margin, futures, options, portfolio margin and FIX trading must
  be off. The private transport allowlists eight account/order endpoints; nothing else is
  reachable. Requests are HMAC-SHA256 signed and timestamped against Binance server time.
- Orders are LIMIT IOC with the durable intent UUID as `newClientOrderId`. Any provider error
  after submission is UNKNOWN and reconciled by client identity; no automatic resubmission.
- Binance takes a BUY fee from the base asset received. Fills are normalized so the ledger stays
  quote-denominated: quantity is the base actually credited and the fee is its USDT value at the
  trade price, so `quantity * price + fee` equals the exact USDT spent. Fees charged in any other
  asset are refused rather than mis-booked.
- Fill identities are deterministic and scoped to account, symbol and native trade ID, avoiding
  collisions between Binance markets and in the global ledger transaction key. Reconciliation
  verifies the approved price/IOC terms, executed quantity, trade identity and exact quote total.
- Price consensus keeps BTC/USDT and ETH/USDT separate from legacy USD pairs. A single Binance
  source has INSUFFICIENT_DATA consensus; no agreement or USDT/USD conversion is fabricated.
- The analyst studies the configured real account's venue: `analyst_portfolio_context.venue`
  (migration 0046) selects Binance or Kraken public data. A proposal analysed for one venue can
  never execute on another.

## Consequences

Binance is the default for connections, analysis, markets, ingestion, backtests and new PAPER
funding (USDT). Historical Kraken fills retain their original venue and currency. 
Position marks route to each fill's own venue. A funded
Binance acceptance test still requires the operator's account and explicit authorization.
