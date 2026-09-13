from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from wallybot.domain.token_risk import (
    SecurityAnalysisResult,
    TokenRiskScore,
    TokenRiskStatus,
    score_token_risk,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def make_result(**overrides: Any) -> SecurityAnalysisResult:
    fields: dict[str, Any] = {
        "token_id": "BONK",
        "chain": "solana",
        "mint_authority_active": None,
        "freeze_authority_active": None,
        "liquidity_locked": None,
        "buy_tax_pct": None,
        "sell_tax_pct": None,
        "is_honeypot": None,
        "malicious_labels": None,
        "source": "goplus",
        "fetched_at": NOW,
    }
    fields.update(overrides)
    return SecurityAnalysisResult(**fields)


def test_a_provider_that_checked_nothing_yields_insufficient_data() -> None:
    score = score_token_risk(make_result(), NOW)
    assert score.status is TokenRiskStatus.INSUFFICIENT_DATA
    assert score.risk_score is None


def test_every_dimension_clean_yields_a_low_risk_score() -> None:
    result = make_result(
        mint_authority_active=False,
        freeze_authority_active=False,
        liquidity_locked=True,
        buy_tax_pct=Decimal("1"),
        sell_tax_pct=Decimal("1"),
        is_honeypot=False,
        malicious_labels=(),
    )
    score = score_token_risk(result, NOW)
    assert score.status is TokenRiskStatus.SCORED
    assert score.risk_score == Decimal("2")


def test_an_active_mint_authority_adds_risk() -> None:
    score = score_token_risk(make_result(mint_authority_active=True), NOW)
    assert score.status is TokenRiskStatus.SCORED
    assert score.risk_score == Decimal("25")
    assert any("mint authority is still active" in reason for reason in score.reasons)


def test_an_active_freeze_authority_adds_risk() -> None:
    score = score_token_risk(make_result(freeze_authority_active=True), NOW)
    assert score.risk_score == Decimal("20")


def test_unlocked_liquidity_adds_risk() -> None:
    score = score_token_risk(make_result(liquidity_locked=False), NOW)
    assert score.risk_score == Decimal("20")


def test_a_honeypot_is_always_critical_regardless_of_other_clean_checks() -> None:
    result = make_result(
        mint_authority_active=False,
        freeze_authority_active=False,
        liquidity_locked=True,
        is_honeypot=True,
    )
    score = score_token_risk(result, NOW)
    assert score.risk_score == Decimal("100")
    assert any("honeypot" in reason for reason in score.reasons)


def test_a_known_malicious_label_is_always_critical() -> None:
    result = make_result(malicious_labels=("rug-pull",))
    score = score_token_risk(result, NOW)
    assert score.risk_score == Decimal("100")
    assert any("rug-pull" in reason for reason in score.reasons)


def test_tax_risk_is_capped_per_dimension() -> None:
    result = make_result(buy_tax_pct=Decimal("50"), sell_tax_pct=Decimal("50"))
    score = score_token_risk(result, NOW)
    assert score.risk_score == Decimal("30")


def test_total_risk_is_the_sum_of_every_triggered_dimension_capped_at_one_hundred() -> None:
    result = make_result(
        mint_authority_active=True,
        freeze_authority_active=True,
        liquidity_locked=False,
        buy_tax_pct=Decimal("50"),
        sell_tax_pct=Decimal("50"),
    )
    score = score_token_risk(result, NOW)
    # 25 (mint) + 20 (freeze) + 20 (liquidity) + 15 (buy tax, capped) + 15 (sell tax, capped) = 95
    assert score.risk_score == Decimal("95")


def test_total_risk_never_exceeds_one_hundred_even_stacked_with_a_honeypot() -> None:
    result = make_result(
        mint_authority_active=True,
        freeze_authority_active=True,
        liquidity_locked=False,
        buy_tax_pct=Decimal("50"),
        sell_tax_pct=Decimal("50"),
        is_honeypot=True,
    )
    score = score_token_risk(result, NOW)
    assert score.risk_score == Decimal("100")


def test_reasons_always_list_the_unscored_dimensions_when_scored() -> None:
    score = score_token_risk(make_result(mint_authority_active=False), NOW)
    assert any("not evaluated" in reason for reason in score.reasons)


def test_a_scored_score_must_carry_a_risk_score() -> None:
    with pytest.raises(ValueError, match="must carry a risk_score"):
        TokenRiskScore(
            token_id="BONK",
            chain="solana",
            version=1,
            status=TokenRiskStatus.SCORED,
            risk_score=None,
            reasons=("x",),
            computed_at=NOW,
        )


def test_an_insufficient_data_score_must_not_carry_a_risk_score() -> None:
    with pytest.raises(ValueError, match="must not carry a risk_score"):
        TokenRiskScore(
            token_id="BONK",
            chain="solana",
            version=1,
            status=TokenRiskStatus.INSUFFICIENT_DATA,
            risk_score=Decimal("10"),
            reasons=("x",),
            computed_at=NOW,
        )


def test_tax_pct_out_of_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        make_result(buy_tax_pct=Decimal("150"))
