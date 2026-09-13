# Phase 11 implementation backlog: Smart Money scoring and clustering

Status: Slice 1 (Smart Money scoring engine + persistence) delivered and verified 2026-09-13. Per
ARCHITECTURE.md's implementation sequence: "Smart Money scoring and clustering, token/whale
intelligence, provider reliability and price consensus." This backlog is provisional past Slice 1,
same discipline as `docs/PHASE_4.md`/`docs/PHASE_10.md`: each further slice gets its own design
pass when actually started, not committed to upfront.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | `score_smart_money` (pure, FIFO-matched realized PnL/win-rate) + append-only persistence | Unit + property tests; integration tests for insert-only history |
| 2 | Smart Money clustering (independent wallets converging on the same asset) | Not started |
| 3 | Token intelligence (`TokenRiskScore` from `SecurityAnalysisProvider`) | Not started |
| 4 | Whale intelligence (large-transfer/exchange-flow signals) | Not started |
| 5 | Provider reliability tracking + price consensus across independent feeds | Not started |

**This session implements Slice 1 only.**

## Delivered: Slice 1 — Smart Money scoring engine

Per ARCHITECTURE.md: "Never classify a wallet as Smart Money merely because it had one profitable
trade." The wider spec names ~20 analysis dimensions (realized/unrealized PnL, win rate, profit
factor, drawdown, a Sharpe-like risk adjustment, trade count, wallet age, holding duration,
consistency, token quality, entry/exit liquidity and timing, rug/scam/wash-trading exposure,
portfolio concentration, market-regime performance). This codebase has a real data source
(`WalletActivityEvent`, Phase 10 Slice 5) for exactly five of them: realized PnL, win rate, trade
count, wallet age and holding period. Building a formula that silently ignored the other fifteen
while still returning a confident 0-100 number would misrepresent what was actually evaluated —
so this slice scores only what it can support and lists everything else, by name, as not
evaluated in every snapshot's `reasons`.

- `wallybot/domain/smart_money.py` (pure): `_match_fifo_trades` — DATA.md's own "documented FIFO
  lot convention initially for realized PnL," applied to on-chain BUY/SELL events instead of
  exchange fills (the earliest open BUY lot for a token is the one a later SELL closes against
  first; events with no `price` are ignored, not guessed at). `CompletedTrade` (realized PnL,
  holding period). `score_smart_money(wallet_id, events, now)`: a wallet with fewer than
  `MIN_COMPLETED_TRADES` (5) realized round trips gets `SmartMoneyStatus.INSUFFICIENT_DATA` and no
  score at all — the structural enforcement of "never ... merely because it had one profitable
  trade" — otherwise `SCORED` with a score in `[0, 100]` from a 60/40 win-rate/realized-PnL
  weighting. **That 60/40 split and the $1,000 PnL normalization are an explicitly-labeled
  versioned placeholder, not a backtested calibration** — nothing downstream consumes this score
  for any financial decision yet (it is Phase 10/11's OBSERVE-only research signal), and RISK.md's
  "do not invent universally safe market thresholds" applies the moment anything ever does.
  `SmartMoneyScoreSnapshot` is immutable and self-validating (a `SCORED` snapshot must carry an
  in-range score; an `INSUFFICIENT_DATA` one must not carry any score at all).
- `wallybot/infrastructure/models.py` + `migrations/versions/0006_smart_money.py`:
  `SmartMoneyScoreSnapshotRow` / `smart_money_score_snapshots` — no unique constraint at all on
  `wallet_id`, deliberately: a fresh evaluation is always a new row, timestamped by `computed_at`,
  never an update. `wallybot/infrastructure/smart_money_repository.py`:
  `SmartMoneyScoreRepository.save` only ever inserts; `latest`/`history` read it back.
- `tests/unit/test_smart_money.py`: insufficient-data threshold (including the single-profitable-
  trade case the spec explicitly calls out), correct win rate/PnL for a scored snapshot, mixed
  wins/losses, FIFO lot ordering (a real bug caught while writing the FIFO test itself — see the
  test's own comment — a shared token name silently mixed two otherwise-independent lot queues),
  ignoring priceless events, and `SmartMoneyScoreSnapshot`'s own construction invariants.
- `tests/property/test_smart_money_invariants.py` (Hypothesis): across arbitrary round-trip price
  sequences, the score (when present) always stays in `[0, 100]`, the status always matches
  whether the completed-trade count clears the minimum, and scoring the same events twice is
  byte-for-byte deterministic — matching this codebase's existing "deterministic, versioned
  scoring" principle (`score_momentum`'s own docstring).
- `tests/integration/test_smart_money_persistence.py` (Testcontainers): round-trip, a second
  snapshot never overwrites the first (both remain in `history`, `latest` returns the newer one),
  and an `INSUFFICIENT_DATA` snapshot round-trips correctly with no score.

Verified: full suite 331 passed (317→331), ruff/pyright clean, domain purity confirmed
(`smart_money.py` imports only stdlib + `wallybot.domain.validation`/`wallet_activity`), migration
applied and verified against the live `wallybot-api` container (head `0006_smart_money`).

Explicitly not built in Slice 1: no clustering (Slice 2), no token/whale intelligence (Slices 3-4),
no provider reliability/price consensus (Slice 5), no wiring of a `SmartMoneyScoreSnapshot` into
any signal, strategy or the decision pipeline (`docs/DECISION_PIPELINE.md`) — this score is
observable, not yet actionable, matching Phase 10's OBSERVE-only scope. No scheduler computes
scores automatically; a caller decides when to call `score_smart_money` and save the result, same
as `WalletMonitoringService`/`ReconciliationService` only provide their operations, not a
scheduler.
