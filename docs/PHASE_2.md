# Phase 2 implementation backlog

Status: Slices 1-4 (market domain model + FakeExchange; universe filters; data quality gate; Redis
hot-tier caching) implemented and verified on 2026-09-12. Slices 5-9 are a documented backlog only
— not started. See [ARCHITECTURE](../ARCHITECTURE.md) for how Phase 2 fits the overall
implementation sequence, and [PHASE_1](PHASE_1.md) for the completed authenticated-foundation phase
this builds on.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | Market domain model (`Instrument`, `Candle`) + `MarketDataProvider` port + seeded `FakeExchange` | Contract test suite passes against FakeExchange; unit tests for value validation |
| 2 | Instrument universe filters (min history, liquidity, spread) + versioned config | Unit tests reject unavailable/illiquid/wide-spread instruments per [DATA.md](../DATA.md) |
| 3 | Data quality gate (PASS/WARNING/FAILURE, reason codes) on fetched candles | Unit tests for each validation rule in DATA.md "Market quality" |
| 4 | Redis hot-tier caching of validated snapshots ([ADR-003](adr/003-redis.md)) | Integration test: cache populated, expiry never implies staleness bypass |
| 5 | Historical Parquet writer + manifest ([ADR-005](adr/005-historical-storage.md)) | Integration test: partitioned write, checksum, atomic publish |
| 6 | Kraken adapter via CCXT, passing the same contract suite | Contract test suite passes against Kraken (sandbox/testnet or recorded fixtures) |
| 7 | Streaming (native Kraken WS vs CCXT Pro benchmark per [ADR-004](adr/004-exchange-adapters.md)) | Reconnect/sequence-gap/staleness fault tests |
| 8 | `FeatureEngine` port + versioned features from as-of data | Unit tests: no future-observation leakage |
| 9 | Scanner (universe ranking, finalist selection) | Unit tests on synthetic ranked datasets |

Slices are ordered by dependency: nothing downstream (quality, caching, history, streaming,
features, the scanner) has anything to consume until instruments and candles exist as typed,
tested values with at least one working adapter. Each slice gets its own contract/unit/integration
tests before being marked delivered here — no phase silently promotes a strategy or skips its
required test layer (see [TESTING](../TESTING.md)).

## Delivered: Slice 1 — market domain model + FakeExchange

- `wallybot/domain/clock.py`: `Clock` protocol (injectable time source; no capability needed a
  second implementation yet, so only the port exists).
- `wallybot/domain/market.py`: `MarketType`, `Instrument` (frozen, venue+market_type+base+quote
  identity, positive increments), `Candle` (frozen, aware-UTC timestamps, OHLC bounds, finite
  positive prices, nonnegative volume), `MarketDataProvider` protocol (`discover_instruments`,
  `fetch_candles`). Zero FastAPI/SQLAlchemy/CCXT imports, per this repo's domain-purity rule.
- `wallybot/exchanges/fake.py`: `FakeExchange` — seeded, deterministic, network-free
  `MarketDataProvider` for two instruments (`BTC/USD`, `ETH/USD` on a `"fake"` venue). Scoped to
  market-data methods only; balances/order/fill simulation is deferred to the Phase 4
  paper-execution slice, once execution actually needs a `FakeExchange` capable of it.
- `tests/contract/market_data_provider_suite.py` + `tests/contract/test_fake_exchange.py`: the
  shared contract suite any `MarketDataProvider` (Fake today, Kraken later) must satisfy.
- `tests/unit/test_market_domain.py`: value-object validation.

Explicitly not built in Slice 1: universe filters, data quality gating across a series (gaps,
staleness, abnormal returns), Redis/Parquet wiring, any Kraken/CCXT adapter, streaming, features,
the scanner. Each is a separate future slice above.

## Delivered: Slice 2 — instrument universe filters

- `wallybot/domain/market.py`: added `MarketSnapshot` (bid/ask, aware-UTC timestamp, rejects a
  crossed market) and a `spread_ratio` property, and extended `MarketDataProvider` with
  `fetch_snapshot` — `ARCHITECTURE.md`'s own port description already said "fetch candles/
  snapshots"; Slice 1 just didn't need the snapshot half yet.
- `wallybot/exchanges/fake.py`: `FakeExchange.fetch_snapshot` — deterministic seeded bid/ask around
  the same base price used for candles.
- `wallybot/market/universe.py` (new capability package, per `ARCHITECTURE.md`'s planned layout):
  `UniverseFilterConfig` (versioned thresholds — min history, min average quote volume, max spread
  ratio, per DATA.md's "Universe minimum history/liquidity and spread limits are versioned
  configuration"), `evaluate_instrument`/`evaluate_universe` (return per-instrument eligibility +
  reason codes: `insufficient_history`, `illiquid`, `unavailable`, `wide_spread`), and
  `eligible_instruments` to extract the accepted list.
- Contract suite extended with `assert_fetches_valid_snapshot`; `tests/unit/test_universe.py` for
  the four rejection reasons plus the eligible case.

Explicitly not built in Slice 2: the stateful, cross-candle data-quality gate (gaps, duplicates,
staleness, abnormal returns, PASS/WARNING/FAILURE with evidence) — that is Slice 3, and conflating
single-snapshot spread checks with a full quality gate here would make neither testable in
isolation. No caching or persistence of evaluations yet either — nothing consumes them until a
scanner or scheduler exists to call this on a cadence.

## Delivered: Slice 3 — data quality gate

- `wallybot/domain/market.py`: extracted the timeframe→duration mapping (previously private to
  `FakeExchange`) into a public `TIMEFRAME_DURATIONS` constant, so both the adapter and the quality
  gate share one source of truth instead of duplicating it (DRY).
- `wallybot/data/quality.py` (new capability package): `QualityStatus` (PASS/WARNING/FAILURE),
  `QualityIssue` (reason code + evidence string + derived severity), `QualityReport`,
  `QualityPolicy` (versioned thresholds: max stale age, max clock drift, max abnormal return, plus
  the timeframe the series is expected to match), and `evaluate_series_quality` — checks ordering,
  duplicate timestamps, timeframe-boundary alignment, gaps, staleness, clock drift (impossible vs.
  merely delayed) and abnormal close-to-close returns, per DATA.md's "Market quality" section.
  `wrong_timeframe`, `not_ordered`, `duplicate_timestamps`, `misaligned_timestamp`,
  `gap_detected`, `stale` and `clock_drift_impossible` are always blocking (FAILURE) — DATA.md
  names gaps, staleness and failed synchronization as blocking explicitly, and an unordered/
  duplicated/misaligned series can't be trusted either. `clock_drift` (delayed but not impossible)
  and `abnormal_return` are WARNING — structurally sound but statistically notable signals a
  policy may choose to tolerate.
- `tests/unit/test_quality.py`: one test per reason code, plus a clean-series PASS case and the
  two WARNING-only cases (confirming they don't escalate to FAILURE on their own).

Explicitly not built in Slice 3: no Redis caching of quality reports, no Parquet quarantine
writing for FAILURE-graded data, no wiring into a scheduler that runs this on a cadence — that
begins with Slice 4/5, once there's a caller that actually fetches live candles on a timer.

## Delivered: Slice 4 — Redis hot-tier caching of validated snapshots

- `wallybot/infrastructure/market_cache.py` (new, in `infrastructure/` since this is the first
  real I/O adapter in Phase 2 — everything before this slice was pure domain/capability code):
  `RedisLike` (a narrow `Protocol` for just the `get`/`set` calls this class needs, so tests can
  pass a plain in-memory stub instead of depending on the concrete `redis.asyncio.Redis` type —
  the same port-not-implementation discipline as `Clock`/`MarketDataProvider`) and `MarketCache`
  (`set_snapshot`/`get_snapshot`, JSON-serialized, keyed by `instrument.id`).
- Per ADR-003 ("cache expiry never implies valid fresh market data"), `MarketCache` deliberately
  has no method that claims freshness — it stores and returns exactly what it was given, including
  the original timestamp. A cache *hit* is not proof the data is current; callers still run the
  Slice 3 quality gate or check `snapshot.timestamp` themselves.
- `tests/integration/test_market_cache.py` (real Redis via testcontainers, reusing the existing
  `dependencies` fixture from `tests/integration/conftest.py`): populate-then-read, miss returns
  `None`, TTL actually expires (had to switch from `EX` to `PX` — Redis's `EX` only accepts
  whole-second TTLs, which broke a sub-second test), and the key acceptance-criteria test:
  a stale (but unexpired) snapshot comes back with its stale timestamp unchanged, proving the
  cache never launders staleness into freshness.

Explicitly not built in Slice 4: no caching of candles or quality reports (only snapshots, per this
slice's row); no cache invalidation policy beyond TTL; no wiring into a scheduler yet — that is
still downstream of a scanner or scheduler slice that doesn't exist.
