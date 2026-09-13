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
| 4 | Provider ports + at least one real adapter (e.g. one on-chain data provider) | Not started |
| 5 | On-chain event ingestion (webhook/subscription preferred over polling) | Not started |

**This session implements Slices 1, 2 and 3.**

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
