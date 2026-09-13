# Phase 11 implementation backlog: Smart Money scoring and clustering

Status: Slices 1-3 delivered and verified 2026-09-13. Per ARCHITECTURE.md's implementation
sequence: "Smart Money scoring and clustering, token/whale intelligence, provider reliability and
price consensus." This backlog is provisional past Slice 3, same discipline as
`docs/PHASE_4.md`/`docs/PHASE_10.md`: each further slice gets its own design pass when actually
started, not committed to upfront.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | `score_smart_money` (pure, FIFO-matched realized PnL/win-rate) + append-only persistence | Unit + property tests; integration tests for insert-only history |
| 2 | Smart Money clustering (independent wallets converging on the same asset) | Unit + property tests; integration tests for insert-only history |
| 3 | Token intelligence (`TokenRiskScore` from `SecurityAnalysisProvider`) | Unit + property tests; integration tests for insert-only history; port + fake only (no real vendor key) |
| 4 | Whale intelligence (large-transfer/exchange-flow signals) | Not started |
| 5 | Provider reliability tracking + price consensus across independent feeds | Not started |

**This session implements Slices 1, 2 and 3.**

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

## Delivered: Slice 2 — Smart Money clustering

Per ARCHITECTURE.md's example: "3 unrelated Smart Money wallets buy the same token within 30
minutes." The wider spec also names liquidity change, volume change, holder change, price
movement and market-regime context as inputs to a cluster signal's confidence. This codebase's
data source (`WalletActivityEvent`) supports wallet identity, action, value, price and timing —
not the market-condition dimensions — so, following the same "honest partial evaluation" principle
as Slice 1, every emitted signal lists those five dimensions, by name, as `not evaluated` in its
`reasons` rather than folding them into a fabricated confidence number.

- `wallybot/domain/smart_money_cluster.py` (pure): `SmartMoneyClusterSignal` (immutable,
  self-validating — at least two wallets, unique wallet IDs, independent count within range, a
  non-negative window, positive value/price, `independence_score`/`confidence` in `[0, 1]`, at
  least one reason, aware datetimes). `_independent_groups` enforces "do not count multiple wallets
  controlled by the same entity as independent confirmations" by collapsing wallets that share a
  known `entity_id` into one participant — wallets with no known entity link always count as
  independent from each other, since identity we have not proven common is never assumed common.
  `detect_smart_money_clusters(events_by_wallet, entity_by_wallet, action, window,
  min_independent_wallets=3)`: a documented single left-to-right sweep per `(chain, token)` market
  — the window anchored at each not-yet-consumed event grows to include every later event of the
  same action within `window`; when enough independent wallets appear a signal fires and the sweep
  jumps past every event it used, so no wallet's transaction is ever claimed by two overlapping
  signals; otherwise it slides forward by one event. This is a known, documented simplification (it
  can miss a cluster that only forms by combining the tail of one candidate window with events just
  past it) — not a claim of finding every cluster that ever existed in the data.
- `wallybot/infrastructure/models.py` + `migrations/versions/0007_smart_money_clusters.py`:
  `SmartMoneyClusterSignalRow` / `smart_money_cluster_signals` — insert-only, same reasoning as
  `SmartMoneyScoreSnapshotRow`: each detection run's output is a fact about a moment in time, never
  a correction of an earlier one. `wallybot/infrastructure/smart_money_cluster_repository.py`:
  `SmartMoneyClusterRepository.save` only ever inserts; `history_for_token`/`latest` read it back.
- `tests/unit/test_smart_money_cluster.py`: three independent wallets within the window produce a
  signal; two never meet the default minimum; wallets outside the window don't cluster; wallets
  sharing an entity collapse to one independent participant and can suppress or dilute a cluster
  without pushing it over the threshold; a later, unrelated fourth wallet from the same entity as
  one of three still lets the other three cluster; a signal never reuses an event already claimed
  by an earlier signal in the same sweep; only the requested action is considered; and
  `SmartMoneyClusterSignal`'s own construction invariants.
- `tests/property/test_smart_money_cluster_invariants.py` (Hypothesis): across arbitrary wallet
  counts, offsets and prices, every emitted signal stays within its declared bounds
  (`independence_score`/`confidence` in `[0, 1]`, `independent_wallet_count` between 3 and the
  wallet count, `window_end - window_start <= window`, positive value/price), no wallet is ever
  claimed by two signals, and detecting twice over the same input is byte-for-byte deterministic.
- `tests/integration/test_smart_money_cluster_persistence.py` (Testcontainers): round-trip, a
  second signal never overwrites the first (both remain in `history_for_token`), and
  `history_for_token` filters correctly by `(chain, token)`.

Verified: full suite 346 passed (331→346), ruff clean, pyright clean on all new/changed files (a
pre-existing, unrelated pyright backlog in `test_security.py`/`auth_routes.py`/
`system_routes.py`/`tests/integration/conftest.py` predates this slice and was left untouched),
domain purity confirmed (`smart_money_cluster.py` imports only stdlib +
`wallybot.domain.validation`/`wallet_activity`), migration applied and verified against the live
`wallybot-api` container (head `0007_smart_money_clusters`, `/health/ready` returns `ready`).

Explicitly not built in Slice 2: no wiring of `entity_by_wallet` lookups against the real
`EntityRepository`/`WalletRepository` (the function takes the mapping as a plain argument — a
future caller, not this slice, is responsible for assembling it from persisted wallet
attributions), no scheduler or service that calls `detect_smart_money_clusters` automatically, no
wiring of a `SmartMoneyClusterSignal` into any signal, strategy or the decision pipeline — same
OBSERVE-only scope as Slice 1's score. No token/whale intelligence (Slices 3-4), no provider
reliability/price consensus (Slice 5).

## Delivered: Slice 3 — Token intelligence (`TokenRiskScore`)

Per ARCHITECTURE.md's Contracts table: "Token/contract safety checks (mint/freeze authority,
liquidity locks, honeypot indicators) feeding TokenRiskScore," and the "Token intelligence"
section, which also names market cap, FDV, liquidity, holder concentration, contract/pool/
developer-wallet age, buy/sell tax and known malicious labels. No `SecurityAnalysisProvider`
vendor (GoPlus, Honeypot.is, TokenSniffer, RugCheck, ...) is integrated — the same "blocked on a
real API key" situation as Phase 10 Slice 4b's wallet/entity vendors — so, like that slice, this
one delivers the port and a pure scoring function plus a seeded fake, not a real adapter. Market
cap/FDV are already real via `MarketMetadataProvider` (Phase 10 Slice 4c) but measure size, not
safety, so they are deliberately not folded into this score.

- `wallybot/domain/token_risk.py` (pure): `SecurityAnalysisResult` (one provider's raw safety
  check output — every field `None` when not checked, matching `TokenMarketMetadata`'s own
  convention), `SecurityAnalysisProvider` port, `TokenRiskStatus`, `TokenRiskScore` (immutable,
  self-validating: `SCORED` needs an in-range `risk_score`, `INSUFFICIENT_DATA` must not carry
  one). `score_token_risk(result, now)`: scores only the dimensions the provider actually reported
  — a provider that reported nothing at all yields `INSUFFICIENT_DATA`, never a fabricated "looks
  safe" zero. Higher `risk_score` means riskier (0-100), the opposite polarity from Smart Money's
  score, since this number is meant to gate entry rather than rank quality. A honeypot or a known
  malicious label forces `risk_score` to 100 regardless of any other clean check — these are
  binary disqualifiers, not another point on a weighted scale. Holder concentration and
  contract/pool/developer-wallet age are listed in every scored snapshot's `reasons` as
  `UNSCORED_DIMENSIONS`: no provider in this codebase, real or fake, models them yet. **The
  per-dimension point weights (mint 25, freeze 20, unlocked liquidity 20, tax capped at 15 each)
  are an explicitly-labeled versioned placeholder, not a backtested calibration** — same caveat as
  Slice 1's 60/40 split; nothing consumes this score for any financial decision yet.
- `wallybot/intelligence/fake.py`: `FakeSecurityAnalysisProvider` — an unseeded token gets an
  all-`None` result (not an exception), matching `FakeWalletIntelligenceProvider`'s "unknown wallet
  returns empty, never raises" contract; a real scanner always answers a valid query, it just may
  have nothing to report.
- `wallybot/infrastructure/models.py` + `migrations/versions/0008_token_risk.py`:
  `TokenRiskScoreRow` / `token_risk_scores` — insert-only, no unique constraint on
  `(chain, token_id)`, same reasoning as `SmartMoneyScoreSnapshotRow`.
  `wallybot/infrastructure/token_risk_repository.py`: `TokenRiskScoreRepository.save` only ever
  inserts; `latest`/`history` read it back.
- `tests/unit/test_token_risk.py`: insufficient-data when nothing was checked, a fully-clean token
  scores low, each dimension's independent risk contribution, honeypot/malicious-label override to
  100 regardless of other clean checks, per-dimension tax capping, total-risk capping, and
  `TokenRiskScore`'s own construction invariants.
- `tests/property/test_token_risk_invariants.py` (Hypothesis): across arbitrary combinations of
  present/absent dimensions, the score (when present) always stays in `[0, 100]`, status always
  matches whether anything was actually checked, a honeypot or malicious label always forces 100,
  and scoring the same result twice is byte-for-byte deterministic.
- `tests/contract/security_analysis_provider_suite.py` + `tests/contract/
  test_fake_security_analysis_provider.py` (same shared-suite pattern as
  `wallet_intelligence_provider_suite.py`).
- `tests/integration/test_token_risk_persistence.py` (Testcontainers): round-trip, a second score
  never overwrites the first, and an `INSUFFICIENT_DATA` score round-trips with no `risk_score`.

Verified: full suite 368 passed (346→368), ruff clean, pyright clean on every new/changed file (the
same pre-existing, unrelated pyright backlog noted in Slice 2 is untouched), domain purity
confirmed (`token_risk.py` imports only stdlib + `wallybot.domain.validation`), migration applied
and verified against the live `wallybot-api` container (head `0008_token_risk`, `/health/ready` →
`ready`).

Explicitly not built in Slice 3: no real `SecurityAnalysisProvider` adapter (blocked on a vendor
API key, same as Slice 4b), no wiring of a `TokenRiskScore` into any speculative-allocation gate,
strategy or the decision pipeline despite ARCHITECTURE.md's stated intent ("gating any speculative
proposal before risk evaluation") — that wiring is real future work, not implied by this slice's
scope. No whale intelligence (Slice 4), no provider reliability/price consensus (Slice 5).
