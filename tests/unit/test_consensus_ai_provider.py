from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from wallybot.domain.features import FeatureVector
from wallybot.domain.market import Instrument, MarketType
from wallybot.domain.regime import Regime, RegimeClassification
from wallybot.domain.trade_proposal import AIAnalysisContext, TradeDirection, TradeProposal
from wallybot.intelligence.consensus_ai_provider import ConsensusAiProvider

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)
INSTRUMENT = Instrument(
    venue="kraken",
    market_type=MarketType.SPOT,
    base="BTC",
    quote="USD",
    price_increment=Decimal("0.01"),
    quantity_increment=Decimal("0.0001"),
    min_quantity=Decimal("0.0001"),
)


class FixedProvider:
    def __init__(self, proposal: TradeProposal | None) -> None:
        self.proposal = proposal

    async def analyze(self, context: AIAnalysisContext) -> TradeProposal | None:
        return self.proposal


def context() -> AIAnalysisContext:
    features = FeatureVector(
        instrument=INSTRUMENT,
        timeframe="1h",
        as_of=AS_OF,
        version=1,
        values={"momentum": Decimal("1")},
    )
    return AIAnalysisContext(
        instrument=INSTRUMENT,
        features=features,
        regime=RegimeClassification(
            instrument=INSTRUMENT,
            as_of=AS_OF,
            version=1,
            regime=Regime.TRENDING_UP,
            reason="test",
        ),
        strategy_signals=(),
        as_of=AS_OF,
    )


def proposal(
    proposal_id: str,
    model_id: str,
    entry_price: Decimal,
    confidence: Decimal = Decimal("0.8"),
    direction: TradeDirection = TradeDirection.LONG,
) -> TradeProposal:
    stop_price = entry_price * (
        Decimal("0.95") if direction is TradeDirection.LONG else Decimal("1.05")
    )
    take_profit_price = entry_price * (
        Decimal("1.10") if direction is TradeDirection.LONG else Decimal("0.90")
    )
    return TradeProposal(
        proposal_id=proposal_id,
        instrument=INSTRUMENT,
        direction=direction,
        strategy_id="analyst",
        confidence=confidence,
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=entry_price,
        stop_price=stop_price,
        take_profit_price=take_profit_price,
        time_horizon=timedelta(days=1),
        signal_ttl=timedelta(hours=1),
        reasons=(f"{model_id} evidence",),
        risks=("volatility",),
        supporting_signal_ids=(model_id,),
        invalidating_conditions=(),
        source_event_ids=(),
        model_id=model_id,
        prompt_version="v1",
        as_of=AS_OF,
    )


async def test_strict_consensus_combines_two_nearby_recommendations_conservatively() -> None:
    provider = ConsensusAiProvider(
        providers=(
            FixedProvider(proposal("codex-proposal", "codex", Decimal("100"), Decimal("0.9"))),
            FixedProvider(proposal("claude-proposal", "claude", Decimal("101"), Decimal("0.7"))),
        )
    )

    result = await provider.analyze(context())

    assert result is not None
    assert result.proposal_id == "codex-proposal"
    assert result.model_id == "consensus:codex+claude"
    assert result.confidence == Decimal("0.7")
    assert result.reasons[-1] == "Consenso independiente: codex, claude"
    assert "codex evidence" in result.reasons
    assert "claude evidence" in result.reasons


async def test_consensus_preserves_both_analysts_invalidating_conditions():
    first = replace(
        proposal("one", "codex", Decimal(100)), invalidating_conditions=("Pierde soporte",)
    )
    second = replace(
        proposal("two", "claude", Decimal(100)),
        invalidating_conditions=("Pierde soporte", "Desaparece el volumen"),
    )
    result = await ConsensusAiProvider((FixedProvider(first), FixedProvider(second))).analyze(
        context()
    )
    assert result is not None
    assert result.invalidating_conditions == ("Pierde soporte", "Desaparece el volumen")


async def test_strict_consensus_fails_closed_when_one_analyst_holds_or_is_unavailable() -> None:
    provider = ConsensusAiProvider(
        providers=(
            FixedProvider(proposal("codex-proposal", "codex", Decimal("100"))),
            FixedProvider(None),
        )
    )

    assert await provider.analyze(context()) is None


async def test_strict_consensus_fails_closed_when_entry_prices_materially_disagree() -> None:
    provider = ConsensusAiProvider(
        providers=(
            FixedProvider(proposal("codex-proposal", "codex", Decimal("100"))),
            FixedProvider(proposal("claude-proposal", "claude", Decimal("105"))),
        )
    )

    assert await provider.analyze(context()) is None


async def test_strict_consensus_fails_closed_when_analysts_disagree_on_direction() -> None:
    provider = ConsensusAiProvider(
        providers=(
            FixedProvider(proposal("codex-proposal", "codex", Decimal("100"))),
            FixedProvider(
                proposal(
                    "claude-proposal",
                    "claude",
                    Decimal("100"),
                    direction=TradeDirection.SHORT,
                )
            ),
        )
    )

    assert await provider.analyze(context()) is None
