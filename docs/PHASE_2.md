# Phase 2 implementation backlog

Status: Slices 1-2 (market domain model + FakeExchange; universe filters) implemented and verified
on 2026-09-12. Slices 3-9 are a documented backlog only — not started. See
[ARCHITECTURE](../ARCHITECTURE.md) for how Phase 2 fits the overall implementation sequence, and
[PHASE_1](PHASE_1.md) for the completed authenticated-foundation phase this builds on.

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
