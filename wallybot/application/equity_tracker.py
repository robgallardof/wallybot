"""Real equity/PnL tracking from the ledger, closing the gap `DecisionPipeline`'s own docstring
flags: "there is no equity or PnL tracker yet -- a caller supplies `RiskEnvironment` and
`PortfolioState` from whatever it currently knows." Builds a `PortfolioState` (for the allocator/
risk engine's bucket-headroom math) and a fresh `wallybot.domain.equity.EquitySnapshot` (for
RISK.md's persisted daily/weekly loss and high-water-mark drawdown) from one mark-to-market pass
over the ledger -- never two different pricing sources for the same tick.

Every held position is attributed to a single `bucket` -- `DecisionPipelineConfig` is still
single-bucket per run, the same simplification the rest of Phase 3 already uses; per-instrument
bucket assignment across multiple concurrent buckets is a separate, larger change this does not
attempt, since nothing in this schema persists which bucket a position belongs to yet.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.equity import (
    EquitySnapshot,
    compute_daily_loss,
    compute_drawdown,
    compute_weekly_loss,
    next_high_water_mark,
)
from wallybot.domain.market import MarketDataProvider
from wallybot.domain.portfolio import Bucket, PortfolioState
from wallybot.infrastructure.equity_snapshot_repository import EquitySnapshotRepository
from wallybot.infrastructure.portfolio_repository import PortfolioRepository

# Covers both the daily (24h) and weekly (7d) boundary lookups with one bounded query.
_HISTORY_WINDOW = timedelta(days=8)


class UnpricedPositionError(ValueError):
    """A held position has no current market instrument/snapshot to value it with. RISK.md:
    "Missing trustworthy valuation blocks risk increases" -- raised rather than silently
    excluding the position and under-stating equity."""


@dataclass(frozen=True)
class EquityAssessment:
    portfolio_state: PortfolioState
    daily_loss: Decimal
    weekly_loss: Decimal
    drawdown: Decimal


async def assess_equity(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    account_id: str,
    environment: str,
    cash_currency: str,
    bucket: Bucket,
    now: datetime,
    persist: bool = True,
) -> EquityAssessment:
    async with sessions() as db:
        balances = await PortfolioRepository(db).list_balances(account_id)

    cash = sum(
        (b.amount for b in balances if b.purpose == "CASH" and b.currency == cash_currency),
        Decimal(0),
    )
    held = {b.currency: b.amount for b in balances if b.purpose == "POSITION" and b.amount > 0}

    asset_exposure: dict[str, Decimal] = {}
    if held:
        instruments_by_base = {
            instrument.base: instrument
            for instrument in await provider.discover_instruments()
            if instrument.quote == cash_currency
        }
        for currency, quantity in held.items():
            instrument = instruments_by_base.get(currency)
            if instrument is None:
                raise UnpricedPositionError(
                    f"no {currency}/{cash_currency} instrument to value the held position"
                )
            snapshot = await provider.fetch_snapshot(instrument)
            mid_price = (snapshot.bid + snapshot.ask) / 2
            asset_exposure[instrument.id] = quantity * mid_price

    equity = cash + sum(asset_exposure.values(), Decimal(0))
    if equity <= 0:
        raise ValueError(f"computed non-positive equity ({equity}) for account {account_id!r}")

    portfolio_state = PortfolioState(
        equity=equity,
        bucket_exposure=({bucket: sum(asset_exposure.values(), Decimal(0))} if held else {}),
        asset_exposure=asset_exposure,
        open_positions=len(asset_exposure),
    )

    async with sessions() as db:
        repo = EquitySnapshotRepository(db)
        previous = await repo.latest(account_id, environment)
        history = await repo.recent(account_id, environment, now - _HISTORY_WINDOW)

    high_water_mark = next_high_water_mark(previous, equity)
    daily_loss = compute_daily_loss(history, equity, now)
    weekly_loss = compute_weekly_loss(history, equity, now)
    drawdown = compute_drawdown(equity, high_water_mark)

    if persist:
        async with sessions.begin() as db:
            await EquitySnapshotRepository(db).save(
                EquitySnapshot(
                    account_id=account_id,
                    environment=environment,
                    equity=equity,
                    high_water_mark=high_water_mark,
                    recorded_at=now,
                )
            )

    return EquityAssessment(
        portfolio_state=portfolio_state,
        daily_loss=daily_loss,
        weekly_loss=weekly_loss,
        drawdown=drawdown,
    )
