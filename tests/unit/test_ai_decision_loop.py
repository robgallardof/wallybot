"""The AI analysis loop must be unable to create or submit an order."""

import ast
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import wallybot.application.ai_decision_loop as ai_decision_loop
from wallybot.data.quality import QualityPolicy
from wallybot.domain.market import (
    TIMEFRAME_DURATIONS,
    Candle,
    Instrument,
    MarketSnapshot,
    MarketType,
)
from wallybot.market.universe import UniverseFilterConfig


def test_analysis_loop_has_no_execution_or_balance_dependencies() -> None:
    source = inspect.getsource(ai_decision_loop)
    tree = ast.parse(source)
    imported = {
        name
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module]
            if isinstance(node, ast.ImportFrom) and node.module
            else []
        )
    }
    forbidden = (
        "wallybot.application.execution_service",
        "wallybot.exchanges.fake",
        "wallybot.infrastructure.portfolio_repository",
        "wallybot.domain.order",
    )
    assert not any(name.startswith(forbidden) for name in imported)
    assert "OrderIntent" not in source
    assert "execution.submit" not in source


class _HourAlignedClosedCandles:
    """Mimics Kraken: hour-aligned rows after `since`, never the in-progress candle."""

    def __init__(self, instrument, now) -> None:
        self.instrument = instrument
        self.now = now

    async def discover_instruments(self):
        return [self.instrument]

    async def fetch_candles(self, instrument, timeframe, since, limit):
        step = TIMEFRAME_DURATIONS[timeframe]
        open_time = since.replace(minute=0, second=0, microsecond=0) + step
        candles = []
        price = Decimal("100")
        while open_time + step <= self.now:
            price += Decimal("1")
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=open_time,
                    close_time=open_time + step,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=Decimal("10"),
                    source="kraken",
                    received_at=self.now,
                )
            )
            open_time += step
        return candles[-limit:]

    async def fetch_snapshot(self, instrument):
        return MarketSnapshot(
            instrument=instrument,
            bid=Decimal("120"),
            ask=Decimal("120.01"),
            timestamp=self.now,
            source="kraken",
        )


class _RecordingAnalyst:
    def __init__(self) -> None:
        self.instruments: list[str] = []

    async def analyze(self, context):
        self.instruments.append(context.instrument.id)
        return None


async def test_analysts_are_consulted_when_only_closed_candles_are_returned() -> None:
    """Regression: a 20-hour lookback yields 19 closed Kraken candles, so the universe filter
    rejected every instrument and no analyst was ever called."""
    now = datetime(2026, 10, 12, 7, 31, tzinfo=UTC)
    instrument = Instrument(venue="kraken", market_type=MarketType.SPOT, base="XBT", quote="USD")
    analyst = _RecordingAnalyst()

    result = await ai_decision_loop.run_ai_decision_tick(
        sessions=None,  # type: ignore[arg-type]  # nothing is persisted when analysts HOLD
        provider=_HourAlignedClosedCandles(instrument, now),
        ai_provider=analyst,
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        owner_id="owner",
        now=now,
    )

    assert analyst.instruments == [instrument.id]
    assert result.instruments_evaluated == 1


class _TwoInstruments(_HourAlignedClosedCandles):
    def __init__(self, instruments, now) -> None:
        super().__init__(instruments[0], now)
        self.instruments = instruments

    async def discover_instruments(self):
        return list(self.instruments)


class _BuyingAnalyst(_RecordingAnalyst):
    async def analyze(self, context):
        self.instruments.append(context.instrument.id)
        assert context.starter_position is True
        return object()


class _Repository:
    saved: list = []

    def __init__(self, db) -> None:
        pass

    async def save(self, proposal, owner_id=None) -> None:
        self.saved.append(proposal)


class _Sessions:
    def begin(self):
        return self

    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


async def test_starter_request_persists_only_one_proposal(monkeypatch) -> None:
    now = datetime(2026, 10, 12, 7, 31, tzinfo=UTC)
    instruments = [
        Instrument(venue="binance", market_type=MarketType.SPOT, base=base, quote="USDT")
        for base in ("BTC", "ETH")
    ]
    analyst = _BuyingAnalyst()
    _Repository.saved = []
    monkeypatch.setattr(ai_decision_loop, "TradeProposalRepository", _Repository)

    result = await ai_decision_loop.run_ai_decision_tick(
        sessions=_Sessions(),  # type: ignore[arg-type]
        provider=_TwoInstruments(instruments, now),
        ai_provider=analyst,
        quality_policy=QualityPolicy(
            version=1,
            timeframe="1h",
            max_stale_age=timedelta(hours=3),
            max_clock_drift=timedelta(minutes=5),
            max_abnormal_return=Decimal("0.5"),
        ),
        universe_config=UniverseFilterConfig(
            version=1,
            min_history_candles=20,
            min_average_quote_volume=Decimal("0"),
            max_spread_ratio=Decimal("0.05"),
        ),
        owner_id="owner",
        now=now,
        starter_position=True,
    )

    assert result.instruments_evaluated == 2
    assert len(analyst.instruments) == 1
    assert result.proposals_persisted == 1 and len(_Repository.saved) == 1


async def test_open_positions_are_reviewed_even_outside_the_finalists() -> None:
    now = datetime(2026, 10, 12, 7, 31, tzinfo=UTC)
    instruments = [
        Instrument(venue="binance", market_type=MarketType.SPOT, base=base, quote="USDT")
        for base in ("BTC", "ETH")
    ]
    analyst = _RecordingAnalyst()
    original = ai_decision_loop.MAX_FINALISTS
    ai_decision_loop.MAX_FINALISTS = 1
    try:
        result = await ai_decision_loop.run_ai_decision_tick(
            sessions=None,  # type: ignore[arg-type]  # analysts HOLD, nothing persisted
            provider=_TwoInstruments(instruments, now),
            ai_provider=analyst,
            quality_policy=QualityPolicy(
                version=1,
                timeframe="1h",
                max_stale_age=timedelta(hours=3),
                max_clock_drift=timedelta(minutes=5),
                max_abnormal_return=Decimal("0.5"),
            ),
            universe_config=UniverseFilterConfig(
                version=1,
                min_history_candles=20,
                min_average_quote_volume=Decimal("0"),
                max_spread_ratio=Decimal("0.05"),
            ),
            owner_id="owner",
            now=now,
            portfolio_holdings=(("BTC", Decimal("0.001")), ("ETH", Decimal("0.01"))),
        )
    finally:
        ai_decision_loop.MAX_FINALISTS = original

    assert result.instruments_evaluated == 2
    assert sorted(analyst.instruments) == sorted(item.id for item in instruments)
