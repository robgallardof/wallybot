# Deterministic risk and execution policy

Status: baseline requirements for Phases 3–4; no trading is implemented. Defaults come from the supplied specification and require validation before any LIVE rollout. They are constraints, not claims of investment performance.

## Invariants

AI cannot bypass RiskEngine. Research cannot trade. A REJECTED assessment cannot execute. No autonomous withdrawal capability exists. Intent retries cannot create duplicate economic orders. Financial state must reconcile. LIVE is never the default. Invalid/stale data blocks trading. Asset, bucket and cluster concentration is bounded. Financial decisions retain reproducible evidence.

## Initial policy

| Setting | Initial value | Interpretation |
| --- | --- | --- |
| Maximum daily loss | 2% | UTC day, cash-flow-adjusted mark-to-market loss |
| Maximum weekly loss | 5% | UTC Monday start, cash-flow-adjusted mark-to-market loss |
| Maximum drawdown | 10% | Cash-flow-adjusted equity high-water mark |
| Core / Growth / Speculative | 70% / 20% / 10% | Baseline ceilings/targets, never investment obligations |
| Speculative operating maximum | 10% | Protected configured ceiling |
| Absolute speculative maximum | 15% | Hard ceiling; ordinary runtime changes cannot exceed it |
| Single speculative asset | 3% | Conservative initial choice within requested 3–4%; aggregate across venues |
| Open positions | 1 | Aggregate positions plus reserved new entries |
| Leverage / futures / shorting | 1x / OFF / OFF | Spot, no borrowing, no negative inventory |

The 15% absolute ceiling does not automatically authorize an increase from 10%. Such a change needs reviewed configuration, fresh MFA and explicit operator action. Limits for liquidity, spread, slippage, quote age, reconciliation age, per-trade stop risk, asset and cluster exposure must be configured and validated for a venue/timeframe before that strategy is eligible. Missing required limits fail closed; do not invent universally safe market thresholds.

Group assets across venues for concentration. Cash remains separately reported even when assigned to Core; stablecoins have issuer/depeg risk and are not identical to fiat. Neutral and risk-off regimes may reduce ceilings (for example 80/15/5 or 95–100/0–5/0). A strategy cannot raise a protected ceiling merely by selecting a regime label.

## Loss calculations and sizing

Use equity including realized and unrealized PnL net of charged costs, valued with fresh conservative executable prices. Adjust day/week starting equity and high-water marks for external cash flows through a unitized equity series. Persist boundaries and high-water marks so restarting cannot reset losses. Missing trustworthy valuation blocks risk increases. Equality at a limit triggers the breaker.

For a long spot proposal, compute stop-risk quantity as `risk_budget / (entry_price - stop_price + per_unit_cost_buffer)`. Require finite positive equity, risk budget, prices and stop distance. Final quantity is the minimum of stop-risk quantity, cash capacity after costs, asset/bucket/cluster remaining capacity, volatility cap and liquidity/impact capacity. Subtract open-order reservations before sizing. Round quantity down to the instrument step, recompute all bounds and reject if below minimum amount/notional. AI confidence never directly sizes an order. A stop is not a guaranteed execution price; stress gaps and slippage separately.

## Approval contract and checks

Risk receives an immutable proposed intent plus account equity, positions, reservations, fresh market data, regime, quality result, exchange status, reconciliation status and protected policy version. Output is APPROVED, REJECTED or APPROVED_WITH_REDUCED_SIZE, with final quantity, reason codes, input hashes/versions and expiry. Zero-sized approvals are rejected.

Checks run deterministically: mode/authority; schema and finite values; fresh valid data; exchange/instrument support; reconciliation health; active circuit breakers; cash and position capacity; daily/weekly/drawdown losses; asset/bucket/cluster/spec ceilings; volatility/correlation; spread/liquidity/slippage; precision and minimum notional. For optional AI, a malformed decision cannot become an executable recommendation. AI-required strategies HOLD on unavailable AI; explicitly non-AI strategies may continue under their own versioned rules.

Persist approval with reservation in the account transaction. Executor loads the durable approval, verifies intent digest, expiry and policy version, then rechecks time-sensitive controls. Changed state requires renewed risk evaluation. Never allow a request to reuse approval for another asset, quantity, side, mode or account. A rejected decision has no executable intent.

Market appreciation can cause actual exposure to breach a ceiling without a new order. Guarantee that approvals never increase exposure above the ceiling under their conservative valuation; do not claim that prices cannot drift beyond it. On passive breach, freeze additions, alert and evaluate a separate reduction intent. Pending orders, fees, partial fills and exchange precision are included in property tests.

## Breakers and emergency operations

Breakers include losses, drawdown, stale data, abnormal spreads/volatility, exchange outages, repeated execution errors, unknown orders, mismatches, DB failure and clock drift. Persist latch/reason/time. Recovery requires healthy evidence; hard loss/drawdown, ambiguity and reconciliation breakers require operator acknowledgment with fresh MFA. A scheduler cannot silently reset a breaker at midnight.

| Action | Effect |
| --- | --- |
| PAUSE NEW TRADES | Block entries and additions; continue monitoring, reconciliation and separately validated reductions |
| CANCEL OPEN ORDERS | Request cancellations and reconcile races; does not close filled positions |
| CLOSE ALL POSITIONS | Explicitly confirmed reduction intents with execution checks; not guaranteed immediate liquidation |
| EMERGENCY STOP | Revoke normal execution lease and latch emergency; default request cancellation of exposure-increasing orders, preserve protective orders; no automatic liquidation |

Risk-reducing intents use a separate deterministic policy: cannot exceed held quantity, borrow, reverse a position or increase exposure. Loss and allocation breakers may permit reductions; invalid/stale data still forbids pricing/submission of trades. Cancellation is an order-management action and may proceed during stale-price conditions when exchange identity/connectivity is reliable. Outage means an attempted emergency action may remain pending; UI must report actual results. Explicitly cancelling all orders warns that protective orders are included.

Pyramiding requires profit, renewed evidence, original thesis validity and full reapproval; it never bypasses aggregate limits. Profit harvesting and speculative scaling remain experiment parameters until tested. Full Kelly, live arbitrage and autonomous limit relaxation are excluded.

## Evidence before LIVE

Require risk/unit/property tests, exchange adapter contracts, failure recovery and paper/replay ledger reconciliation to pass. A strategy progresses DRAFT → BACKTESTED → VALIDATED → PAPER → CANDIDATE → LIVE → RETIRED with immutable artifacts and human promotion. Predeclare evaluation windows and thresholds, compare BTC/ETH/cash/passive portfolio, include costs and uncertainty, and evaluate drawdown and concentration of returns. Backtest profits alone are insufficient. Start small only after explicit activation; no document here authorizes placing a real trade.
