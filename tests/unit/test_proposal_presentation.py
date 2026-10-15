from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from wallybot.application.proposal_presentation import (
    ProposalDisplayContext,
    display_context,
    proposal_notification,
    rank_proposals,
    risk_label,
)
from wallybot.infrastructure.live_models import AnalystPortfolioRow, LiveControlRow
from wallybot.infrastructure.models import ControlRow, TradeProposalRow

NOW = datetime(2026, 10, 15, 18, tzinfo=UTC)


def proposal(**overrides) -> TradeProposalRow:
    fields = dict(
        proposal_id="proposal-1",
        owner_id="owner",
        venue="binance",
        base="BTC",
        quote="USDT",
        direction="LONG",
        confidence=Decimal("0.8"),
        suggested_allocation_pct=Decimal("0.05"),
        entry_price=Decimal(100),
        stop_price=Decimal(98),
        take_profit_price=Decimal(110),
        time_horizon_seconds=Decimal(86400),
        signal_ttl_seconds=Decimal(3600),
        as_of=NOW,
        reasons=["Impulso respaldado por volumen"],
        risks=["Una caída del mercado invalida la señal"],
        invalidating_conditions=["Cierre por debajo del soporte"],
        decision_status="PENDING",
        execution_status=None,
        execution_environment=None,
        execution_reasons=[],
    )
    fields.update(overrides)
    return TradeProposalRow(**fields)


def context(**overrides):
    fields = dict(
        environment="LIVE",
        live_version=3,
        venue="binance",
        quote="USDT",
        equity=Decimal(1000),
        cash=Decimal(200),
        max_order=Decimal(40),
        as_of=NOW,
    )
    fields.update(overrides)
    return ProposalDisplayContext(**fields)


def test_ranking_uses_reward_risk_before_target_and_active_before_history():
    high_target = proposal(
        proposal_id="high-target", stop_price=Decimal(90), take_profit_price=Decimal(130)
    )
    better_ratio = proposal(proposal_id="better-ratio")
    expired = proposal(
        proposal_id="expired",
        signal_ttl_seconds=Decimal(1),
        as_of=NOW - timedelta(minutes=1),
        take_profit_price=Decimal(200),
    )
    decided = proposal(proposal_id="decided", decision_status="APPROVED")
    missing = proposal(proposal_id="missing", stop_price=None)
    ranked = rank_proposals([expired, high_target, decided, missing, better_ratio], NOW)
    assert [row.proposal_id for row in ranked[:3]] == ["better-ratio", "high-target", "missing"]


@pytest.mark.parametrize(
    "stop,allocation,expected",
    [
        ("98", "0.05", "LOW"),
        ("97.99", "0.05", "MEDIUM"),
        ("95", "0.10", "MEDIUM"),
        ("94.99", "0.05", "HIGH"),
        ("99", "0.11", "HIGH"),
        (None, "0.01", "HIGH"),
    ],
)
def test_risk_labels_have_explicit_boundaries(stop, allocation, expected):
    row = proposal(
        stop_price=Decimal(stop) if stop else None, suggested_allocation_pct=Decimal(allocation)
    )
    assert risk_label(row) == expected


def test_card_explains_amount_scenarios_evidence_horizon_and_expiry():
    card = proposal_notification(proposal(), 1, context(), NOW)
    for expected in [
        "#1",
        "COMPRAR BTC/USDT",
        "LIVE",
        "Riesgo: LOW",
        "40.00 USDT",
        "objetivo de asignación 50.00",
        "efectivo observado 200.00",
        "Por qué: Impulso",
        "Riesgos concretos:",
        "Se invalida si:",
        "10.00%",
        "2.00%",
        "5.00:1",
        "+4.00 / -0.80 USDT",
        "24.00 horas",
        "2026-10-15 19:00:00 UTC",
        "/approve proposal-1",
    ]:
        assert expected in card.text
    assert card.reply_markup["inline_keyboard"][0][0]["callback_data"] == (
        "approve:proposal-1:LIVE:3"
    )
    assert "MFA" not in card.text


@pytest.mark.parametrize(
    "overrides", [dict(quote="USD"), dict(venue="kraken"), dict(equity=None), dict(cash=None)]
)
def test_no_monetary_estimate_for_missing_or_mismatched_valuation(overrides):
    card = proposal_notification(proposal(), 1, context(**overrides), NOW)
    assert "Importe no disponible" in card.text
    assert "Importe orientativo:" not in card.text


def test_available_cash_caps_amount_and_zero_is_not_missing():
    for cash, expected in [(Decimal(10), "10.00 USDT"), (Decimal(0), "0.00 USDT")]:
        card = proposal_notification(proposal(), 1, context(cash=cash), NOW)
        assert f"Importe orientativo: {expected}" in card.text
    card = proposal_notification(proposal(), 1, context(cash=Decimal(10)), NOW)
    assert "faltan 30.00 USDT" in card.text


@pytest.mark.parametrize(
    "overrides",
    [
        dict(decision_status="APPROVED"),
        dict(signal_ttl_seconds=Decimal(1), as_of=NOW - timedelta(seconds=1)),
    ],
)
def test_decided_and_expired_cards_have_no_action_buttons(overrides):
    card = proposal_notification(proposal(**overrides), 1, context(), NOW)
    assert card.reply_markup is None
    assert "/approve" not in card.text


def test_missing_levels_and_sell_are_not_presented_as_comparable_returns():
    for row in [proposal(stop_price=None, take_profit_price=None), proposal(direction="SHORT")]:
        card = proposal_notification(row, 1, context(), NOW)
        assert "Beneficio/riesgo:" not in card.text
        assert "Escenario bruto:" not in card.text


@pytest.mark.parametrize("language", ["es", "en"])
def test_large_analyst_text_is_bounded_and_buttons_fit_telegram(language):
    row = proposal(
        proposal_id="b" * 64,
        reasons=["x" * 5000] * 100,
        risks=["y" * 5000] * 100,
        invalidating_conditions=["z" * 5000] * 100,
        execution_status="BLOCKED",
        execution_reasons=["r" * 5000] * 100,
    )
    card = proposal_notification(row, 1, context(), NOW, language)
    assert len(card.text.encode("utf-16-le")) // 2 <= 4096
    assert card.reply_markup is None  # Commands still work for IDs too long for callback_data.
    assert "/approve " in card.text


@pytest.mark.parametrize(
    "stale,future,ready",
    [(True, False, True), (False, True, True), (False, False, False), (False, False, True)],
)
async def test_display_valuation_requires_recent_ready_owner_context(stale, future, ready):
    timestamp = (
        NOW + timedelta(seconds=1) if future else NOW - timedelta(seconds=61 if stale else 0)
    )
    control = ControlRow(environment="LIVE")
    live = LiveControlRow(
        owner_id="owner",
        connection_id="connection",
        version=3,
        enabled=True,
        state="READY" if ready else "BLOCKED",
        max_order_usd=Decimal(40),
    )
    portfolio = AnalystPortfolioRow(
        owner_id="owner", venue="binance", cash_usd=Decimal(200), as_of=timestamp
    )
    db = AsyncMock()
    db.get.side_effect = [control, live, portfolio]
    from wallybot.domain.equity import EquitySnapshot

    snapshot = EquitySnapshot("live:connection", "LIVE", Decimal(1000), Decimal(1000), timestamp)
    with patch(
        "wallybot.application.proposal_presentation.EquitySnapshotRepository.latest",
        new=AsyncMock(return_value=snapshot),
    ):
        result = await display_context(db, "owner", NOW)
    assert (result.equity is not None) == (not stale and not future and ready)
    assert result.binding == "LIVE:3"
