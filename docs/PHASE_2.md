# Phase 2 implementation backlog

Status: Slices 1-6, 8 and 9 implemented and verified on 2026-09-12 (market domain model +
FakeExchange; universe filters; data quality gate; Redis hot-tier caching; historical Parquet
writer; real Kraken adapter; feature engine; scanner). **Only Slice 7 (streaming) remains.** It
was initially assumed Slice 6 needed user-provided Kraken credentials — that was wrong; Kraken's
market-data endpoints (discovery, candles, ticker) are public and unauthenticated, only
trading/balance endpoints need an API key, and this session had real network access to verify that
directly against the live API. See [ARCHITECTURE](../ARCHITECTURE.md) for how Phase 2 fits the
overall implementation sequence, and [PHASE_1](PHASE_1.md) for the completed
authenticated-foundation phase this builds on.

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

## Delivered: Slice 5 — historical Parquet writer + manifest

- Added `pyarrow` as a new project dependency (pinned `>=23.0.1,<26` — 20.0.0, the version `uv`
  first resolved, had a known CVE; `pip-audit` catches this and every future dependency addition
  should be checked the same way before committing).
- `wallybot/domain/id_generator.py`: `IdGenerator` protocol (injectable ID source, same
  reproducible-tests discipline as `Clock`) — the first capability that needed one.
- `wallybot/data/historical.py` (new): `PartitionManifest` and `HistoricalStore.write_partition`.
  Writes `data/market/<venue>/<BASE>_<QUOTE>/<timeframe>/date=<date>/part-<id>.parquet` (matches
  DATA.md's own example path), finalized via temp-file-then-`os.replace` for both the Parquet file
  and its sidecar `.manifest.json` — atomic publish, never a half-written file visible at the final
  path. OHLCV columns use `pyarrow.decimal128(18, 8)`, not float, so the "never use float for
  money" rule holds all the way into the Parquet schema; pyarrow rejects a Decimal that overflows
  that precision rather than silently truncating it. The manifest records schema version, source,
  acquisition window (min open_time/max close_time), row count, the quality status from Slice 3's
  gate, and a sha256 of the written file. A second write for the same instrument/timeframe/date
  (a correction) gets a new `part_id` and a new file — it never overwrites a prior part.
- `tests/unit/test_historical.py` (uses `tmp_path`, no Docker needed): partition path structure,
  the manifest's sha256 actually matches the written bytes, no leftover `.tmp-*` files after a
  write, rejects empty/mixed-instrument/mixed-date input, and confirms a correction produces two
  distinct parts rather than an overwrite.

Explicitly not built in Slice 5: no per-partition-directory aggregate catalog (DATA.md's
`dataset_manifests` table is Postgres-owned metadata for the research phase, out of scope here —
this slice's manifest is a per-part sidecar, not a repo-wide index); no DuckDB read path yet (that
consumes what this slice produces, but nothing calls this writer on a real schedule yet either);
no compaction/retention policy.

## Delivered: Slice 8 — feature engine (taken out of order; see status note above)

- `wallybot/domain/features.py`: `FeatureVector` (instrument, timeframe, as_of, version,
  named values), `LookaheadError` (a distinct exception type, not a generic `ValueError`, so a
  caller can specifically catch "this would have leaked the future" separately from other
  validation failures), and the `FeatureEngine` protocol — per `ARCHITECTURE.md`'s Contracts
  table: "Versioned features from validated as-of data; no future observations."
- `wallybot/features/simple.py`: `SimpleFeatureEngine` — plain-Python SMA and momentum over a
  trailing window, no NumPy/Pandas/TA-Lib (`ARCHITECTURE.md`'s Technology decisions defer those to
  the research extra "before adoption" evaluation; nothing here needed them yet). Every candle
  passed in is checked against `as_of`: one closing later raises `LookaheadError` rather than
  being silently dropped, so a caller's bug surfaces immediately instead of quietly producing a
  feature that peeked at the future.
- `tests/unit/test_features.py`: hand-calculated SMA/momentum values, confirms only the trailing
  window is used (older candles beyond the window don't affect the result), the lookahead
  rejection, insufficient-history and mixed-instrument rejections.

Explicitly not built in Slice 8: no volatility/realized-vol feature (adds `Decimal.sqrt()`
complexity for no consumer yet), no feature versioning migration path (only `version=1` exists —
a real second version arrives when an actual formula changes), no wiring into a scanner or
strategy yet (Slice 9 is next).

## Delivered: Slice 9 — the scanner

- `wallybot/scoring/simple.py` (new package — explicitly named in `ARCHITECTURE.md`'s planned
  layout): `Score` (instrument id, version, value, the `FeatureVector` it came from) and
  `score_momentum` — the simplest possible deterministic, versioned score (just reads the
  momentum feature back out). No ML, no randomness: the same feature vector always produces the
  same score.
- `wallybot/application/scanner.py` (new package — also explicitly named:
  "application/ # use cases and transaction orchestration"): `scan_universe`, the first capability
  in this repo that composes multiple other capability packages into one use case rather than
  standing alone. Filters the universe (Slice 2), computes features for every eligible instrument
  (Slice 8), scores them (this slice), ranks by score descending, and returns the top
  `max_finalists` plus the list of rejected instrument IDs — matching `ARCHITECTURE.md`'s decision
  flow: "universe filters reject... Versioned scoring ranks finalists."
- Documented (not enforced) precondition: `universe_config.min_history_candles` should be `>=
  feature_window`, or an eligible instrument could still have too little history for the feature
  engine. That mismatch is a caller configuration error and is left to raise loudly (an unhandled
  `ValueError` from `SimpleFeatureEngine.compute`) rather than being silently skipped — consistent
  with this repo's "no silent failures" pattern (`LookaheadError` not being swallowed, etc.).
- `tests/unit/test_scoring.py` and `tests/unit/test_scanner.py`: a three-instrument scenario (one
  strong uptrend, one weak downtrend, one with insufficient history) confirms ranking order,
  `max_finalists` truncation, the ineligible instrument appearing in `rejected_instrument_ids`
  instead of finalists, an empty-finalists result when nothing is eligible, and rejection of a
  nonpositive `max_finalists`.

Explicitly not built in Slice 9: no regime classification, no AI advisory step, no allocation or
risk evaluation — those are Phase 3+ per `ARCHITECTURE.md`'s implementation sequence, well past
what "the scanner" itself is scoped to do. No persistence of scan results either; nothing calls
this on a schedule yet.

## Delivered: Slice 6 — real Kraken adapter

- `wallybot/exchanges/kraken.py`: `KrakenExchange`, implementing the same `MarketDataProvider`
  contract as `FakeExchange`, using Kraken's **public, unauthenticated** REST endpoints
  (`/0/public/AssetPairs`, `/0/public/OHLC`, `/0/public/Ticker`) — no API key anywhere, matching
  this port's "never trading credentials" rule. `KrakenTransport` is a narrow `Protocol` (one
  `get(path, params)` method) so tests can swap in a fixture instead of hitting the network,
  mirroring `MarketCache`'s `RedisLike` pattern from Slice 4.
- Kraken's own asset codes are passed through unrenamed (Bitcoin stays `"XBT"`, not `"BTC"`) so
  `instrument.base + instrument.quote` always reconstructs a valid Kraken pair name for
  `fetch_candles`/`fetch_snapshot` — verified directly against real recorded pair names, not
  assumed.
- `tests/contract/test_kraken_exchange.py`: runs the same shared contract suite `FakeExchange`
  passes, replayed against **real Kraken API responses captured on 2026-09-12** (not synthetic
  data) via a `FixtureKrakenTransport` — no live network call during the test run, per TESTING.md:
  "do not depend on... external exchange availability for mandatory tests." Moved the shared
  `FixedClock` test double out of `test_fake_exchange.py` and into
  `tests/contract/market_data_provider_suite.py` so both adapters' contract tests use the same one
  (DRY — it would otherwise be defined identically twice).
- Also manually verified the real `HttpxKrakenTransport` production path end-to-end against the
  live API outside the test suite (discovery, snapshot, and candles all returned real, current
  Kraken data) — the fixture proves the parsing logic is correct against a real response shape,
  and the live run proves the whole adapter actually works, not just its offline replay.

Explicitly not built in Slice 6: no order-book depth (`/0/public/Depth`) — only ticker best
bid/ask, matching `MarketSnapshot`'s current shape from Slice 2; no authenticated endpoints
(balances, trading) — those belong to Phase 4 paper/live execution, a different capability with
its own credential-handling review; no rate-limit backoff or retry policy yet.

**Phase 2 status after this slice: only Slice 7 (streaming) remains** — it needs the
native-Kraken-WebSocket-vs-CCXT-Pro benchmark ADR-004 explicitly defers, a materially different
and larger piece of work than any slice so far, not something to fold into this same pass.
