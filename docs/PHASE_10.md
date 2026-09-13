# Phase 10 implementation backlog: wallet/entity intelligence infrastructure

Status: Slice 1 (Entity/Wallet domain model), Slice 2 (persistence) and Slice 3 (Entity
Correlation Graph) delivered and verified 2026-09-13. Per ARCHITECTURE.md's implementation
sequence: "Wallet/entity intelligence infrastructure -- Entity/Wallet Registry, correlation
graph, on-chain event ingestion; OBSERVE mode only, no execution authority, buildable in parallel
with earlier phases." This backlog is provisional past Slice 3, same discipline as
`docs/PHASE_4.md`: each further slice gets its own design pass when actually started, not
committed to upfront.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | Entity/Wallet/WalletCluster domain model (pure, attribution-based provenance) | Unit tests: construction validation, mandatory attributions, unit-interval scores |
| 2 | PostgreSQL schema + `EntityRepository`/`WalletRepository` | Integration tests: round-trip, upsert-without-duplicating-attributions, cluster insert-only semantics |
| 3 | Entity Correlation Graph (typed relationships between wallet/entity/token/event) | Not started |
| 4 | `WalletIntelligenceProvider` port + `FakeWalletIntelligenceProvider` | Unit + contract tests |
| 4b | A real wallet/entity vendor adapter (Arkham/Nansen/Helius/Birdeye/Whale Alert/Dune/...) | Still blocked on API credentials -- see "Delivered: Slice 4" below |
| 4c | `MarketMetadataProvider` port + real `CoinGeckoMarketMetadataProvider` adapter | Contract-tested against a real recorded response, verified live |
| 5 | On-chain event ingestion (webhook/subscription preferred over polling) | Not started |

**This session implements Slices 1 through 4c.** Slice 4b (a real *wallet/entity* intelligence
adapter specifically) remains blocked on credentials; Slice 4c substitutes a real adapter for the
market-metadata half of the provider list, which needs no key.

## Delivered: Slice 1 — Entity/Wallet/WalletCluster domain model

- `wallybot/domain/entity.py` (pure): `EntityType` (17 values per the spec: person, public
  figure, politician, fund, company, exchange, institution, whale, trader, wallet cluster,
  anonymous wallet, developer, market maker, protocol, ETF, government, custom),
  `VerificationStatus` (unverified/corroborated/verified/disputed), `Attribution` (source,
  optional source-side entity id, confidence, evidence, verification status, observed-at —
  every field ARCHITECTURE.md's "Multi-source intelligence" section requires), `Entity`
  (id, name, type, aliases, description, enabled, confidence/trust/risk/influence scores,
  tags, attributions, created/updated at). An `Entity` cannot be constructed without at least
  one `Attribution` — "never assume an external attribution is absolute truth" is enforced
  structurally, not left to convention. Confidence/trust/risk/influence are normalized to
  `[0, 1]`, matching this codebase's existing `StrategySignal`/`AggregatedSignal` confidence
  convention, not the spec's separately-called-out `0-100` `SmartMoneyScore`/`TokenRiskScore`
  (those arrive with Phase 11 and keep their own, differently-scaled fields).
- `wallybot/domain/wallet.py` (pure): `MonitoringMode` (`OBSERVE`/`AI_EVALUATED`/`MIRROR`,
  defaulting to `OBSERVE` on every new `Wallet` — ARCHITECTURE.md: "every newly created strategy
  or newly tracked wallet/entity defaults to OBSERVE"), `Wallet` (address, chain, optional entity
  link, labels/tags, scores, enabled, allocation/signal-weight ceilings, attributions,
  created/updated at; `id` property is `f"{chain}:{address}"`), `WalletCluster` (two or more
  distinct wallet ids, confidence, evidence, created-at). Performance fields the wider spec names
  on a wallet (historical PnL, win rate, average hold time, trade count, portfolio value,
  `SmartMoneyScore`) are deliberately not modeled here as mutable fields — ARCHITECTURE.md's
  Smart Money Engine section says score snapshots are append-only history, never overwritten,
  which means those belong to their own snapshot record in Phase 11, not fields that get
  silently overwritten in place on the registry entry.
- `wallybot/domain/validation.py`: `require_aware_datetime`/`require_unit_interval`, factored out
  once `entity.py` and `wallet.py` both needed the same two checks, rather than importing
  underscore-prefixed "private" helpers across sibling modules.
- `tests/unit/test_entity.py` + `tests/unit/test_wallet.py`: construction validation for both
  types and `WalletCluster`, mandatory-attribution enforcement, unit-interval score bounds,
  aware-datetime enforcement, `MonitoringMode` defaulting.

## Delivered: Slice 2 — PostgreSQL schema + repositories

- `migrations/versions/0003_intelligence.py` + matching ORM rows in
  `wallybot/infrastructure/models.py`: `entities`, `entity_attributions`, `wallets`,
  `wallet_attributions`, `wallet_clusters`, `wallet_cluster_members`. `wallets` is keyed by
  `(chain, address)` directly, matching the domain object's own identity, rather than a synthetic
  surrogate id. Attribution tables carry `(parent_id..., source, source_entity_id, observed_at)`
  unique constraints — the dedup key a provider re-reporting the same claim needs. Grants follow
  Slice 4-of-Phase-4's precedent: only `wally_worker` gets write access.
- `wallybot/infrastructure/entity_repository.py` / `wallet_repository.py`: `save()` upserts the
  mutable summary row and appends only attributions not already persisted (checked via the same
  dedup key the unique constraint enforces, so a re-save is a safe no-op for unchanged evidence).
  `WalletRepository.save_cluster` is insert-only — a cluster is a point-in-time observation of
  convergence, not a mutable entity, and saving a duplicate id raises rather than silently
  merging or overwriting.
- **Real rough edge repeated, same as Phase 4 Slice 4**: `apps/api/main.py`'s `/health/ready`
  hardcodes the expected Alembic head revision string; bumped to `"0003_intelligence"`. Still
  flagged as a known issue needing a dynamic fix eventually, not resolved here.
- `tests/integration/test_entity_wallet_persistence.py` (Testcontainers, real Postgres):
  entity/wallet round-trips with their attributions; saving twice updates summary fields without
  duplicating an unchanged attribution; a new attribution from a different source is appended,
  not replacing the first; a wallet can reference an entity; a wallet cluster round-trips and a
  second save of the same cluster id raises.

Verified: full suite 271 passed (243→265 after Slice 1, →271 after Slice 2), ruff/pyright clean
on every touched file, domain purity confirmed (`entity.py`/`wallet.py`/`validation.py` import
only stdlib). Migration applied and verified against the live `wallybot-api` container
(`/health/ready` returns `{"status":"ready"}` at head `0003_intelligence`).

## Delivered: Slice 3 — Entity Correlation Graph

- `wallybot/domain/relationship.py` (pure): `NodeReferenceType` (`WALLET`/`ENTITY`/`TOKEN`/
  `EVENT`/`TRANSACTION`), `NodeReference` (a typed id pointing at any of those), `RelationshipType`
  (all 12 the spec names: `OWNS`, `CONTROLS`, `FUNDS`, `TRADED`, `TRANSFERRED_TO`,
  `TRANSFERRED_FROM`, `DEPLOYED`, `HOLDS`, `INVESTED_IN`, `RELATED_TO`, `DISCLOSED_TRADE`,
  `INSIDER_OF`), `Relationship` (a flat, generic edge — source `NodeReference`, type, target
  `NodeReference`, an `Attribution` reused directly from `entity.py` rather than inventing a
  second provenance shape, created-at). `Company`/`Person`/`Fund`/`Exchange` from the wider spec's
  own node-kind list all collapse to `ENTITY` here — `Entity.entity_type` already distinguishes
  them, so a relationship endpoint does not need to repeat that distinction. A `Relationship`
  cannot reference the same node as both source and target. Unlike `Entity`/`Wallet`, a
  `Relationship` is one claim, not an accumulating identity: two independent sources reporting the
  same real-world relationship are two rows, each with its own `Attribution`, not one row
  gathering multiple attributions.
- `migrations/versions/0004_relationships.py` + `RelationshipRow` in
  `wallybot/infrastructure/models.py`: one table, `source_type`/`source_id`/`relationship_type`/
  `target_type`/`target_id` plus the attribution fields embedded directly (no separate join
  table, since a relationship carries exactly one attribution) — "the existing relational schema
  models this initially, a graph database is a later option," per ARCHITECTURE.md.
  `wallybot/infrastructure/relationship_repository.py`: `save` (insert-only — a caller re-saving
  the same id is an error, not a silent merge), `get`, and `find_by_node` (every relationship
  touching a node on either side — the one traversal a correlation graph needs at this stage).
- `tests/unit/test_relationship.py` + `tests/integration/test_relationship_persistence.py`
  (Testcontainers): construction validation (no self-referencing edges, mandatory id, aware
  datetimes), round-trip, duplicate-id rejection, and `find_by_node` returning matches from
  either side while ignoring unrelated nodes.

Verified: full suite 281 passed (271→281), ruff/pyright clean, domain purity confirmed
(`relationship.py` imports only stdlib + `wallybot.domain.entity`/`validation`), migration applied
and verified against the live `wallybot-api` container (head `0004_relationships`,
`/health/ready` returns `{"status":"ready"}`).

Explicitly not built in Slices 1-3: no provider adapters or any real external data source (every
test uses hand-built domain values, never a live API call), no on-chain event ingestion, no Smart
Money scoring (Phase 11), no admin UI, no graph-traversal beyond one-hop `find_by_node` (multi-hop
queries, e.g. "every wallet within two hops of this entity," are left for whenever a real query
pattern needs them — possibly the trigger for actually introducing a graph database, per
ARCHITECTURE.md's own "later option if query patterns actually need one"). This is registry
infrastructure only — nothing in these three slices can read a signal that influences a trade,
let alone place one.

## Delivered: Slice 4 — `WalletIntelligenceProvider` port + fake (real adapter blocked)

- `wallybot/domain/wallet_activity.py` (pure): `OnChainActionType` (all 12 the spec's "On-chain
  monitoring" list names: `BUY`, `SELL`, `SWAP`, `TRANSFER`, `MINT`, `BURN`, `ADD_LIQUIDITY`,
  `REMOVE_LIQUIDITY`, `APPROVE`, `STAKE`, `UNSTAKE`, `BRIDGE`), `WalletActivityEvent` (wallet id,
  chain, transaction hash, token, action, amount, optional value/price/liquidity in USD,
  occurred-at, an `Attribution`). `amount` is always positive; direction lives entirely in
  `action` — this is a normalized *observation*, never an interpretation: "do not interpret a
  large transfer by itself as BUY or SELL... generate a signal and allow strategy intelligence to
  interpret it in context" (ARCHITECTURE.md's whale-intelligence rule) applies to every wallet
  event, not only whale-sized ones. `WalletIntelligenceProvider` Protocol:
  `fetch_wallet_activity(chain, address, since)` and `fetch_wallet_labels(chain, address)`.
- `wallybot/intelligence/fake.py`: `FakeWalletIntelligenceProvider`, a new capability package
  (`wallybot/intelligence/`) alongside `exchanges/`, `risk/`, etc. Unlike `FakeExchange`'s candle
  generator, this fake has no plausible-random-data generator — no real wallet-activity provider
  exists yet to give a generator something to imitate — so it returns exactly what it was
  constructed with, seeded explicitly per wallet, rather than inventing data with no real schema
  to validate against.
- `tests/unit/test_wallet_activity.py`, `tests/contract/wallet_intelligence_provider_suite.py` +
  `test_fake_wallet_intelligence_provider.py` (mirrors `market_data_provider_suite.py`'s
  established pattern: shared assertions, one test module per adapter).

**Real vendor adapter blocked on credentials.** ARCHITECTURE.md's provider list (Arkham, Nansen,
Helius, Birdeye, Whale Alert, Dune, ...) are the intended real implementations of this port, the
same way `KrakenExchange` is `MarketDataProvider`'s real implementation. Unlike Kraken's public
market-data endpoints (verified in Phase 2 to need no credentials at all), every wallet/entity
intelligence vendor in that list requires an API key for any endpoint beyond a trivial free tier,
and none is available in this environment. Building a real adapter now would mean either
fabricating a fixture with no real captured response behind it (this codebase's contract tests are
built specifically to avoid that — see `tests/contract/test_kraken_exchange.py`'s "real recorded
API response" comment) or leaving it untested against anything real, which this session's own
discipline treats as equivalent to not having verified it at all. This is a genuine, named
blocker, not a scope decision — the operator needs to supply a key for at least one of these
providers before Slice 4b can be completed the same way Kraken was.

Verified: full suite 297 passed (281→297), ruff/pyright clean, domain purity confirmed
(`wallet_activity.py` imports only stdlib + `wallybot.domain.entity`/`validation`).

## Delivered: Slice 4c — `MarketMetadataProvider` port + real CoinGecko adapter

User confirmed access to CoinGecko when asked which provider (if any) they had credentials for.
CoinGecko's `/coins/markets` public endpoint needs no API key at all — verified live via `curl`
before writing any code, the same check that unblocked Kraken in Phase 2. This is not a wallet/
entity intelligence provider (Slice 4b, above, is still genuinely blocked); it is the real
implementation of `MarketMetadataProvider`, a port ARCHITECTURE.md's Contracts table already
named as planned before this session's expansion.

- `wallybot/domain/market_metadata.py` (pure): `TokenMarketMetadata` (token id, symbol, name,
  market cap/FDV/24h volume/circulating/total/max supply in USD, all optional and `None` — never
  a fabricated zero — when the provider does not report them; `source`, `source_updated_at` (the
  provider's own claimed freshness) and `fetched_at` (this system's own retrieval time) — the same
  "exchange time vs. received time" distinction `Candle` already makes). `MarketMetadataProvider`
  Protocol: `fetch_token_metadata(token_ids) -> list[TokenMarketMetadata]`.
- `wallybot/market/coingecko.py`: `CoinGeckoMarketMetadataProvider`, with the same injectable-
  transport shape as `wallybot/exchanges/kraken.py` (`CoinGeckoTransport` Protocol +
  `HttpxCoinGeckoTransport`) so tests never depend on live network access. Every numeric field
  converts via `Decimal(str(value))`, never `Decimal(value)` directly on a JSON float, to avoid
  binary floating-point artifacts in what this codebase treats as authoritative money/supply data.
- `tests/unit/test_market_metadata.py`; `tests/contract/test_coingecko.py` using a real recorded
  response (`bitcoin`/`ethereum` from `/coins/markets`, captured 2026-09-13) as a fixture, per
  TESTING.md's "do not depend on external ... availability for mandatory tests" — including
  Ethereum's genuinely-absent `max_supply` staying `None`, not becoming a fabricated `0`.
- **Verified against the live API directly** (not just the fixture), matching this session's
  standing practice for every real adapter: `CoinGeckoMarketMetadataProvider` with a real
  `SystemClock` and the real `HttpxCoinGeckoTransport` correctly fetched and normalized live
  bitcoin/ethereum data with no API key.

Verified: full suite 314 passed (297→314), ruff/pyright clean, domain purity confirmed.

Explicitly not built in Slice 4c: no token security/safety fields (mint authority, liquidity
locks, honeypot indicators — those need a different provider, `SecurityAnalysisProvider`, and are
still Phase 11's `TokenRiskScore` territory), no historical/candle data from CoinGecko (that
remains `MarketDataProvider`'s job, already served by Kraken/Fake), no wiring of this provider
into the decision pipeline or the scanner — this slice only proves the adapter itself works
against the real service.
