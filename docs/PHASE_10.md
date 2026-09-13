# Phase 10 implementation backlog: wallet/entity intelligence infrastructure

Status: Slice 1 (Entity/Wallet domain model) and Slice 2 (persistence) delivered and verified
2026-09-13. Per ARCHITECTURE.md's implementation sequence: "Wallet/entity intelligence
infrastructure -- Entity/Wallet Registry, correlation graph, on-chain event ingestion; OBSERVE
mode only, no execution authority, buildable in parallel with earlier phases." This backlog is
provisional past Slice 2, same discipline as `docs/PHASE_4.md`: each further slice gets its own
design pass when actually started, not committed to upfront.

| Order | Slice | Acceptance evidence |
| --- | --- | --- |
| 1 | Entity/Wallet/WalletCluster domain model (pure, attribution-based provenance) | Unit tests: construction validation, mandatory attributions, unit-interval scores |
| 2 | PostgreSQL schema + `EntityRepository`/`WalletRepository` | Integration tests: round-trip, upsert-without-duplicating-attributions, cluster insert-only semantics |
| 3 | Entity Correlation Graph (typed relationships between wallet/entity/token/event) | Not started |
| 4 | Provider ports + at least one real adapter (e.g. one on-chain data provider) | Not started |
| 5 | On-chain event ingestion (webhook/subscription preferred over polling) | Not started |

**This session implements Slices 1 and 2.**

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

Explicitly not built in Slices 1-2: no Entity Correlation Graph (relationships between wallet/
entity/token/event — Slice 3), no provider adapters or any real external data source (every test
uses hand-built domain values, never a live API call), no on-chain event ingestion, no Smart
Money scoring (Phase 11), no admin UI. This is registry infrastructure only — nothing in these
two slices can read a signal that influences a trade, let alone place one.
