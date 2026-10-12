# ADR-018: Operator-approved real spot trading

Status: accepted, 2026-10-12. Supersedes ADR-017's PAPER-only implementation scope.

The operator explicitly requested real-money trading and will configure the exchange connection
and financial limits in the UI. PAPER is an optional simulator, not the delivery objective.
Human approval, isolation, ownership, expiry, idempotency and deterministic risk requirements
remain mandatory. This does not promote an unattended strategy or authorize a funded test.

## Decision

The first supported venue is Kraken spot, with USD, XBT and ETH. Connections accepts a dedicated
API key and secret with balance/order queries plus create/cancel permissions. The provider's
permission report is verified; funding, withdrawal, address-management, earn and unknown grants
are rejected. Credentials are encrypted and never returned. Linking a key does not activate LIVE.

The deployment capability flag, explicit connection selection, valid positive trade/exposure/loss
limits, fresh MFA and typed LIVE confirmation precede activation. Public prices, private balances,
existing orders and the opening ledger must reconcile. The app imports observed opening balances
as balanced postings, without inventing their historical cost or realized profit.

Each LIVE approval includes the displayed mode and limits version. Approval is committed once;
the real-account service serializes across API instances with a PostgreSQL session advisory lock.
It rechecks ownership, mode, policy, expiry, quality, current balances, loss history, active
breakers, instrument precision/minimums, current fees, price movement and book liquidity. It
submits only an IOC limit order capped by cash/inventory, total exposure and the operator's trade
limit (including the verified fee budget for buys). No leverage or borrowed inventory exists.

The same account/limits and allocation-mandate fingerprint are checked immediately before the
external submission. An ambiguous result is UNKNOWN and never blindly resubmitted. Durable UUID
client identities, bounded closed-order pagination and trade evidence allow the existing execution
service to reconcile fills and ledger postings once, including after restart. Background recovery
continues when execution is disabled. Recovery never automatically clears a blocked execution
state; rearming requires MFA and healthy evidence. Balance mismatches fail closed.

The analyst may read a dated, sanitized cash/holding snapshot, not credentials, account controls,
orders or the ledger. Missing/stale LIVE portfolio context stops proposal generation. The AI has
no gateway and cannot approve or send orders. Telegram review links remain navigation only.

## Practical limits

This release uses the existing CORE allocation/risk pipeline and one open-position ceiling.
Daily loss stops at the stricter operator USD budget or 2%; weekly loss is 5% and drawdown 10%.
Stops/targets remain review levels and do not create automatic protective orders. Arbitrary
external deposits, withdrawals, manual trades, unsupported assets and account switching are not
silently folded into the ledger: a mismatch requires separate reviewed reconciliation. Kraken
keys requiring API-specific OTP are not supported. Broker/equity, futures and other real venues
remain separate work; read-only connections do not imply their trading support.

See [the UI activation runbook](../runbooks/real-spot-trading.md) and
[verification evidence](../stats/testing.md). No claim of strategy profitability or funded live
acceptance is made by unit, scripted-adapter or browser tests.
