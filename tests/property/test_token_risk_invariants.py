from datetime import UTC, datetime
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from wallybot.domain.token_risk import SecurityAnalysisResult, TokenRiskStatus, score_token_risk

NOW = datetime(2026, 1, 1, tzinfo=UTC)

_maybe_bool = st.one_of(st.none(), st.booleans())
_maybe_pct = st.one_of(
    st.none(),
    st.decimals(min_value="0", max_value="100", places=2, allow_nan=False, allow_infinity=False),
)
_maybe_labels = st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=10), max_size=3))


@given(
    mint_authority_active=_maybe_bool,
    freeze_authority_active=_maybe_bool,
    liquidity_locked=_maybe_bool,
    buy_tax_pct=_maybe_pct,
    sell_tax_pct=_maybe_pct,
    is_honeypot=_maybe_bool,
    malicious_labels=_maybe_labels,
)
@settings(max_examples=300)
def test_score_is_always_bounded_and_status_matches_whether_anything_was_checked(
    mint_authority_active,
    freeze_authority_active,
    liquidity_locked,
    buy_tax_pct,
    sell_tax_pct,
    is_honeypot,
    malicious_labels,
):
    result = SecurityAnalysisResult(
        token_id="BONK",
        chain="solana",
        mint_authority_active=mint_authority_active,
        freeze_authority_active=freeze_authority_active,
        liquidity_locked=liquidity_locked,
        buy_tax_pct=buy_tax_pct,
        sell_tax_pct=sell_tax_pct,
        is_honeypot=is_honeypot,
        malicious_labels=None if malicious_labels is None else tuple(malicious_labels),
        source="fuzzer",
        fetched_at=NOW,
    )
    score = score_token_risk(result, NOW)

    anything_checked = any(
        value is not None
        for value in (
            mint_authority_active,
            freeze_authority_active,
            liquidity_locked,
            buy_tax_pct,
            sell_tax_pct,
            is_honeypot,
            malicious_labels,
        )
    )

    if not anything_checked:
        assert score.status is TokenRiskStatus.INSUFFICIENT_DATA
        assert score.risk_score is None
    else:
        assert score.status is TokenRiskStatus.SCORED
        assert score.risk_score is not None
        assert Decimal(0) <= score.risk_score <= Decimal(100)
        if is_honeypot or malicious_labels:
            assert score.risk_score == Decimal(100)


@given(
    mint_authority_active=_maybe_bool,
    freeze_authority_active=_maybe_bool,
    liquidity_locked=_maybe_bool,
    buy_tax_pct=_maybe_pct,
    sell_tax_pct=_maybe_pct,
    is_honeypot=_maybe_bool,
    malicious_labels=_maybe_labels,
)
@settings(max_examples=100)
def test_scoring_the_same_result_twice_is_deterministic(
    mint_authority_active,
    freeze_authority_active,
    liquidity_locked,
    buy_tax_pct,
    sell_tax_pct,
    is_honeypot,
    malicious_labels,
):
    result = SecurityAnalysisResult(
        token_id="BONK",
        chain="solana",
        mint_authority_active=mint_authority_active,
        freeze_authority_active=freeze_authority_active,
        liquidity_locked=liquidity_locked,
        buy_tax_pct=buy_tax_pct,
        sell_tax_pct=sell_tax_pct,
        is_honeypot=is_honeypot,
        malicious_labels=None if malicious_labels is None else tuple(malicious_labels),
        source="fuzzer",
        fetched_at=NOW,
    )
    first = score_token_risk(result, NOW)
    second = score_token_risk(result, NOW)
    assert first == second
