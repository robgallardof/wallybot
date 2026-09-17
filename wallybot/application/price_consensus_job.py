"""Populates real price-consensus and provider-reliability data from independent market-data
providers -- closing the gap both `wallybot.domain.price_consensus` and
`wallybot.domain.provider_reliability` flag in their own module docstrings: the pure computation
existed with no live, multi-provider caller. The loop wrapper (`_price_consensus_loop`) lives in
`apps/api/main.py`, same split as `_market_ingestion_loop`/`ingest_market_data`: only `apps/api`
has internet egress (`worker`/`scheduler`/`research` are `internal: true`, per PENDING.md's Fase
7), so that is the only process that can run this.

Tiingo has no live quote endpoint (`fetch_snapshot` always raises `NotImplementedError`, per its
own module docstring), so every provider here is queried the same way: the most recently closed
1-minute candle's close price, timestamped at its own close time. Mixing a live bid/ask from one
provider against a stale candle close from another would make staleness/outlier filtering
meaningless, so both sides of the comparison are held to the same standard.

Only two logical pairs are tracked (BTC/USD, ETH/USD) -- the same pairs `KrakenExchange`'s own
default `pairs` already limits ingestion to, and small enough to stay well inside a free-tier rate
limit even polled every few minutes. The saved `instrument_id` is the provider-agnostic pair
string ("BTC/USD"), never one provider's own `Instrument.id` -- a consensus row is about the asset
pair, not any single venue.

Tiingo is never configured via a Docker secret or env var: an operator adds it like any other
market-data credential, through the existing Connections UI (`apps/api/connection_routes.py`,
`provider_connections` table -- `"TIINGO"` was already a valid `provider` value there before this
job existed, added for exactly this). `run_price_consensus_tick` re-checks for a usable Tiingo
connection on every tick rather than deciding once at process start, so adding or removing one
through the UI takes effect on the next tick, no restart required. Kraken needs no credentials and
is passed in once as a long-lived source, same as everywhere else it's used.

Reliability outcomes are kept in memory only (a bounded recent-window per provider, owned by the
caller and threaded through call to call) -- there is no `provider_call_outcomes` table, and
persisting every individual call would be substantial, unused schema for a signal already
summarized by the snapshot this module saves. A process restart resets the window, which only
means a brief `INSUFFICIENT_DATA` reliability status until `MIN_CALLS_FOR_STATUS` calls
accumulate again -- never a wrong status.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from time import monotonic

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wallybot.domain.clock import Clock
from wallybot.domain.market import Instrument, MarketDataProvider, MarketType
from wallybot.domain.price_consensus import (
    PriceConsensusResult,
    PriceQuote,
    compute_price_consensus,
)
from wallybot.domain.provider_reliability import (
    ProviderCallOutcome,
    ProviderReliabilitySnapshot,
    compute_provider_reliability,
)
from wallybot.exchanges.tiingo import HttpxTiingoTransport, TiingoExchange
from wallybot.infrastructure.price_consensus_repository import PriceConsensusRepository
from wallybot.infrastructure.provider_connection_repository import ProviderConnectionRepository
from wallybot.infrastructure.provider_reliability_repository import ProviderReliabilityRepository
from wallybot.security.crypto import Crypto

QUOTE_TIMEFRAME = "1m"
QUOTE_LOOKBACK = timedelta(minutes=5)
MAX_RECENT_OUTCOMES = 50

OutcomeWindow = dict[str, deque[ProviderCallOutcome]]


@dataclass(frozen=True)
class ProviderSource:
    """One market-data provider queried for a pair's most recent price."""

    name: str
    provider: MarketDataProvider


def _instrument(venue: str, base: str) -> Instrument:
    return Instrument(venue=venue, market_type=MarketType.SPOT, base=base, quote="USD")


TRACKED_PAIRS: tuple[tuple[str, dict[str, Instrument]], ...] = (
    ("BTC/USD", {"kraken": _instrument("kraken", "XBT"), "tiingo": _instrument("tiingo", "BTC")}),
    ("ETH/USD", {"kraken": _instrument("kraken", "ETH"), "tiingo": _instrument("tiingo", "ETH")}),
)


async def _fetch_quote(
    source: ProviderSource, instrument: Instrument, now: datetime, outcomes: OutcomeWindow
) -> PriceQuote | None:
    started = monotonic()
    try:
        candles = await source.provider.fetch_candles(
            instrument, QUOTE_TIMEFRAME, now - QUOTE_LOOKBACK, 5
        )
        succeeded = True
    except Exception:
        candles = []
        succeeded = False
    latency_ms = Decimal(str((monotonic() - started) * 1000))
    outcomes.setdefault(source.name, deque(maxlen=MAX_RECENT_OUTCOMES)).append(
        ProviderCallOutcome(source.name, succeeded, latency_ms, now)
    )
    if not succeeded or not candles:
        return None
    latest = max(candles, key=lambda candle: candle.close_time)
    return PriceQuote(source.name, latest.close, latest.close_time)


async def compute_price_consensus_and_reliability(
    sources: list[ProviderSource], now: datetime, outcomes: OutcomeWindow
) -> tuple[list[PriceConsensusResult], list[ProviderReliabilitySnapshot]]:
    """Query every source for every tracked pair, then compute consensus per pair and a
    reliability snapshot per source. No database access -- see :func:`run_price_consensus_tick`
    for the persisting wrapper.

    :param sources: Providers to query; one candle fetch per source per tracked pair.
    :param now: Current time, used for staleness filtering and as every result's timestamp.
    :param outcomes: Per-provider recent-call window, mutated in place across calls.
    :returns: Consensus results (one per tracked pair) and reliability snapshots (one per source
        that has made at least one call so far, across this and prior invocations).
    """
    results: list[PriceConsensusResult] = []
    for canonical_id, per_source_instrument in TRACKED_PAIRS:
        quotes: list[PriceQuote] = []
        for source in sources:
            instrument = per_source_instrument.get(source.name)
            if instrument is None:
                continue
            quote = await _fetch_quote(source, instrument, now, outcomes)
            if quote is not None:
                quotes.append(quote)
        results.append(compute_price_consensus(canonical_id, quotes, now))

    snapshots = [
        compute_provider_reliability(source.name, list(outcomes[source.name]), now)
        for source in sources
        if outcomes.get(source.name)
    ]
    return results, snapshots


async def _tiingo_source(
    sessions: async_sessionmaker[AsyncSession], crypto: Crypto, clock: Clock
) -> tuple[ProviderSource, httpx.AsyncClient] | tuple[None, None]:
    async with sessions() as db:
        connection = await ProviderConnectionRepository(db).latest_with_key("TIINGO")
    if connection is None or not connection.encrypted_key:
        return None, None
    client = httpx.AsyncClient(timeout=10.0)
    provider = TiingoExchange(clock=clock, transport=HttpxTiingoTransport(
        crypto.decrypt(connection.encrypted_key), client
    ))
    return ProviderSource("tiingo", provider), client


async def run_price_consensus_tick(
    sessions: async_sessionmaker[AsyncSession],
    crypto: Crypto,
    clock: Clock,
    static_sources: list[ProviderSource],
    now: datetime,
    outcomes: OutcomeWindow,
) -> None:
    """Compute one round of consensus/reliability and persist it atomically.

    :param sessions: Session factory scoped to the caller's database role.
    :param crypto: Decrypts a Tiingo connection's stored key, if one exists; never logged.
    :param clock: Passed to a freshly-built `TiingoExchange`, if one is added this tick.
    :param static_sources: Providers that need no credentials (Kraken) -- always queried.
    :param now: Current time.
    :param outcomes: Per-provider recent-call window, mutated in place across calls.
    """
    tiingo_source, tiingo_client = await _tiingo_source(sessions, crypto, clock)
    sources = list(static_sources) + ([tiingo_source] if tiingo_source else [])
    try:
        results, snapshots = await compute_price_consensus_and_reliability(sources, now, outcomes)
    finally:
        if tiingo_client is not None:
            await tiingo_client.aclose()
    async with sessions.begin() as db:
        consensus_repo = PriceConsensusRepository(db)
        for result in results:
            await consensus_repo.save(result)
        reliability_repo = ProviderReliabilityRepository(db)
        for snapshot in snapshots:
            await reliability_repo.save(snapshot)
