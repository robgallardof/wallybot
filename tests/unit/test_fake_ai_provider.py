from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.regime import Regime, RegimeClassification
from wallybot.domain.trade_proposal import AIAnalysisContext, TradeDirection, TradeProposal
from wallybot.intelligence.fake_ai import FakeAIProvider

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)
OTHER_INSTRUMENT = Instrument(
    venue="fake",
    market_type=MarketType.SPOT,
    base="ETH",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.001"),
    min_quantity=Decimal("0.001"),
)


def make_context(instrument: Instrument) -> AIAnalysisContext:
    features = FeatureVector(
        instrument=instrument, timeframe="1h", as_of=AS_OF, version=1, values={}
    )
    regime = RegimeClassification(
        instrument=instrument, as_of=AS_OF, version=1, regime=Regime.TRENDING_UP, reason="test"
    )
    return AIAnalysisContext(
        instrument=instrument,
        features=features,
        regime=regime,
        strategy_signals=(),
        as_of=AS_OF,
    )


def make_proposal(instrument: Instrument) -> TradeProposal:
    return TradeProposal(
        proposal_id="prop-1",
        instrument=instrument,
        direction=TradeDirection.LONG,
        strategy_id="ai-v1",
        confidence=Decimal("0.6"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=Decimal("50000"),
        stop_price=Decimal("48000"),
        take_profit_price=Decimal("55000"),
        time_horizon=timedelta(days=1),
        signal_ttl=timedelta(hours=1),
        reasons=("seeded",),
        risks=(),
        supporting_signal_ids=(),
        invalidating_conditions=(),
        source_event_ids=(),
        model_id="fake-model",
        prompt_version="v1",
        as_of=AS_OF,
    )


async def test_seeded_instrument_returns_the_exact_scripted_proposal() -> None:
    proposal = make_proposal(INSTRUMENT)
    provider = FakeAIProvider(proposals={INSTRUMENT: proposal})

    result = await provider.analyze(make_context(INSTRUMENT))

    assert result is proposal


async def test_unseeded_instrument_returns_none_not_a_fabricated_default() -> None:
    provider = FakeAIProvider(proposals={INSTRUMENT: make_proposal(INSTRUMENT)})

    result = await provider.analyze(make_context(OTHER_INSTRUMENT))

    assert result is None


async def test_no_seed_at_all_returns_none() -> None:
    provider = FakeAIProvider()

    result = await provider.analyze(make_context(INSTRUMENT))

    assert result is None
