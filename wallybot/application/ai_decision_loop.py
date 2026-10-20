"""Produce and persist AI recommendations, never orders.

The AI worker is an analyst. It consumes validated market context and saves a dated proposal for
one operator. It has no execution gateway, balance reader, order builder, or withdrawal
capability. A different approval workflow must validate a human decision, the mandate, and the
deterministic controls before a PAPER order can exist (ADR-017).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.application.scanner import scan_universe
from wallybot.data.quality import QualityPolicy, evaluate_series_quality
from wallybot.domain.market import TIMEFRAME_DURATIONS, MarketDataProvider
from wallybot.domain.quality import QualityStatus
from wallybot.domain.regime import classify_regime
from wallybot.domain.strategy import StrategyContext
from wallybot.domain.trade_proposal import AIAnalysisContext, AIProvider
from wallybot.infrastructure.trade_proposal_repository import TradeProposalRepository
from wallybot.market.universe import UniverseFilterConfig
from wallybot.strategies.trend_following import TrendFollowingStrategy

TIMEFRAME = "1h"
# Lookback exceeds FEATURE_WINDOW: providers return only closed, boundary-aligned candles, so an
# exact 20-hour window yields 19 and every instrument failed the minimum-history filter.
HISTORY_CANDLES = 30
FEATURE_WINDOW = 20
MAX_FINALISTS = 5
RISK_OFF_THRESHOLD = Decimal("0.5")
STARTER_CORE_BASES = ("BTC", "ETH")
# Pullback entries: down over the feature window, but less than this (beyond it is a crash).
MAX_PULLBACK = Decimal("0.10")
PULLBACK_CANDIDATES = 3


@dataclass(frozen=True)
class AiDecisionTickResult:
    instruments_evaluated: int
    proposals_received: int
    proposals_persisted: int


async def run_ai_decision_tick(
    sessions: async_sessionmaker[AsyncSession],
    provider: MarketDataProvider,
    ai_provider: AIProvider,
    quality_policy: QualityPolicy,
    universe_config: UniverseFilterConfig,
    owner_id: str,
    now: datetime,
    allocation_guidance: tuple[tuple[str, Decimal], ...] = (),
    portfolio_cash_usd: Decimal | None = None,
    portfolio_holdings: tuple[tuple[str, Decimal], ...] = (),
    portfolio_as_of: datetime | None = None,
    starter_position: bool = False,
    portfolio_positions: Mapping[str, tuple[Decimal, datetime]] | None = None,
    holdings_review: bool = False,
) -> AiDecisionTickResult:
    """Analyze eligible instruments and save explained proposals for one operator only."""
    step = TIMEFRAME_DURATIONS[TIMEFRAME]
    since = now - step * HISTORY_CANDLES
    instruments = await provider.discover_instruments()

    candles_by_id = {}
    snapshots_by_id = {}
    quality_by_id = {}
    for instrument in instruments:
        candles = await provider.fetch_candles(instrument, TIMEFRAME, since, HISTORY_CANDLES)
        candles_by_id[instrument.id] = candles
        snapshots_by_id[instrument.id] = await provider.fetch_snapshot(instrument)
        quality_by_id[instrument.id] = evaluate_series_quality(candles, quality_policy, now)

    scan = scan_universe(
        [item for item in instruments if quality_by_id[item.id].status != QualityStatus.FAILURE],
        candles_by_id,
        snapshots_by_id,
        universe_config,
        now,
        FEATURE_WINDOW,
        MAX_FINALISTS,
    )

    strategy = TrendFollowingStrategy()
    proposals_received = 0
    proposals_persisted = 0
    # Review every open position (HOLD / SELL / add more) before new ideas, even when its
    # momentum no longer ranks it among the finalists.
    held = {asset for asset, quantity in portfolio_holdings if quantity > 0}
    reviews = tuple(score for score in scan.ranked if score.inputs.instrument.base in held)
    # Two entry styles: momentum finalists (trend following) and pullbacks -- the deepest dips
    # that are not a crash (buy low). A starter buy leads with pullbacks, then the core assets.
    momentum_key = f"momentum_{FEATURE_WINDOW}"
    dips = tuple(
        sorted(
            (
                score
                for score in scan.ranked
                if -MAX_PULLBACK < score.inputs.values.get(momentum_key, Decimal(0)) < 0
            ),
            key=lambda score: score.inputs.values[momentum_key],
        )
    )[:PULLBACK_CANDIDATES]
    core = tuple(
        score
        for base in STARTER_CORE_BASES
        for score in scan.ranked
        if score.inputs.instrument.base == base
    )
    ordered = (*dips, *core, *scan.finalists) if starter_position else (*scan.finalists, *dips)
    seen = {score.inputs.instrument.id for score in reviews}
    entries = []
    # A holdings review (/analyze) only asks about what is already held.
    for score in () if holdings_review else ordered:
        if score.inputs.instrument.id not in seen:
            seen.add(score.inputs.instrument.id)
            entries.append(score)
    for score in (*reviews, *entries):
        vector = score.inputs
        instrument = vector.instrument
        average_price, held_since = (portfolio_positions or {}).get(instrument.base, (None, None))
        context = AIAnalysisContext(
            instrument=instrument,
            features=vector,
            regime=classify_regime(vector, RISK_OFF_THRESHOLD),
            strategy_signals=(
                strategy.evaluate(
                    StrategyContext(
                        instrument=instrument,
                        features=vector,
                        regime=classify_regime(vector, RISK_OFF_THRESHOLD),
                        as_of=now,
                    )
                ),
            ),
            as_of=now,
            allocation_guidance=allocation_guidance,
            portfolio_cash_usd=portfolio_cash_usd,
            portfolio_holdings=portfolio_holdings,
            portfolio_as_of=portfolio_as_of,
            starter_position=starter_position,
            bid=snapshots_by_id[instrument.id].bid,
            ask=snapshots_by_id[instrument.id].ask,
            position_average_price=average_price,
            position_held_since=held_since,
            holdings_review=holdings_review,
        )
        proposal = await ai_provider.analyze(context)
        if proposal is None:
            continue
        proposals_received += 1
        async with sessions.begin() as db:
            await TradeProposalRepository(db).save(proposal, owner_id=owner_id)
        proposals_persisted += 1
        if starter_position:
            break  # One starter buy is the whole request; the finalists are ranked best-first.

    return AiDecisionTickResult(
        instruments_evaluated=len(reviews) + len(entries),
        proposals_received=proposals_received,
        proposals_persisted=proposals_persisted,
    )
