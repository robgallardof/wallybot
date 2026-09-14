# Current task

**Task:** Continue closing the "backend exists, nothing shows it" gap per `docs/PENDING.md`'s
recommended delivery order. User said "Continua con el flow y la app ok?" — kept going
autonomously per this session's established pattern (no check-in between slices).

**This session's delivery:** connected the last two Phase 10 OBSERVE-only signals that were not
yet surfaced in the UI — wallet activity (on-chain feed) and the Entity Correlation Graph. Same
end-to-end pattern as Smart Money/whale flow/token risk/provider reliability/price consensus:

- `wallybot/infrastructure/wallet_activity_repository.py`: `list_recent(limit=100)` — newest-first
  across every monitored wallet (previously only had `list_for_wallet`, per-wallet).
- `wallybot/infrastructure/relationship_repository.py`: `list_recent(limit=100)` — newest-first
  across the whole graph (previously only had `find_by_node`, node-scoped traversal).
- `GET /api/intelligence/wallet-activity` and `GET /api/intelligence/entity-graph` in
  `apps/api/intelligence_routes.py` + `apps/api/dto.py`'s `WalletActivityRowView`/
  `WalletActivityView`, `RelationshipRowView`/`EntityGraphView`.
- **Same recurring access-control gap found again** (5th time: 0012/0013/0016/0017/now):
  `wally_api` had no grant on `wallet_activity_events`/`relationships` — migration
  `0018_wallet_relationship_grants` (had to keep the revision id ≤32 chars — Postgres's
  `alembic_version.version_num` column caps at varchar(32); a first, longer id caused
  `StringDataRightTruncation` on `alembic upgrade head`, now known for next time). Bumped
  `apps/api/main.py`'s hardcoded Alembic revision check to
  `"0018_wallet_relationship_grants"` (same recurring rough edge, still not dynamic).
- Frontend: `apps/web/src/lib/dto.ts`'s `walletActivityRowSchema`/`walletActivitySchema`,
  `relationshipRowSchema`/`entityGraphSchema`; `useWalletActivityData.ts`/`useEntityGraphData.ts`;
  `WalletActivitySection.tsx`/`EntityGraphSection.tsx` composed into `IntelligencePage.tsx`
  (no new nav entry needed — same "Inteligencia" page as the other five signals) and wired into
  `Dashboard.tsx`. English strings added to `lib/locales/en.json`.
- Tests: `tests/integration/test_wallet_activity_route.py` + `test_entity_graph_route.py`
  (auth-required + seeded/empty via the real repositories); a new Playwright test in
  `observability.spec.ts` (populated + empty states) plus the two new endpoints added to the
  shared `shell()` fixture's route map (every test that opens `/intelligence` now needs them
  stubbed, since `Dashboard.tsx` fires both hooks unconditionally on that page).

**Verified:** full suite 516 passed (510→516), ruff/pyright clean on every touched file, domain
purity untouched (no domain changes this slice — pure repository/API/frontend wiring), `tsc`/
`eslint`/`next build` clean, full Playwright suite green (9 passed, 1 skipped as always) including
the new wallet-activity/entity-graph test. Rebuilt **both** the `api`-research image and the base
`wallybot-api:0.1.0` image (the `migrate`/`worker`/`scheduler` services share the base image via
docker-compose's `&app` anchor — rebuilding only `api`/`web` is not enough when a new migration
ships; learned this the hard way this session after `migrate` silently ran against a stale image
with no `0018` file present). Migration applied via `docker compose up migrate`, `api` restarted,
`gateway`/`api`/`web` all healthy, `/health/ready` → `{"status":"ready"}` at
`0018_wallet_relationship_grants`, `/login` serving 200 through the gateway. Not yet committed.

**Phase 10 status: now fully surfaced in the UI** — all 5 OBSERVE-only signal families
(Smart Money, whale flow, token risk, provider reliability/price consensus, wallet activity,
entity graph) are visible on the Inteligencia page. Remaining Phase 10 gap: Slice 4b (real
wallet/entity vendor adapter — blocked on an API key decision, per `.ai/HANDOFF.md`).

**What's realistically left for a "finished product"** (unchanged from before this slice, see
`.ai/HANDOFF.md`'s longer list): the Parquet dataset-ingestion job so `POST /api/backtests`
returns non-empty results in production; Phase 12 Slice 4 (real AI adapter, needs an authorized
model/API key decision) + a scheduler actually calling `ShadowDecisionService`; Phases 7/8
(research agents, Telegram); Phase 9 (LIVE trading, gated behind RISK.md/SECURITY.md evidence).

**Immediate next actions:** commit this slice's changes (not yet committed). Then, per
`docs/PENDING.md`'s delivery order, the next body of work is either the Parquet ingestion job
(makes backtests non-empty in production) or Phase 6/12 Slice 4 (needs a model/API key decision
from the user first — cannot proceed on that path without one).
