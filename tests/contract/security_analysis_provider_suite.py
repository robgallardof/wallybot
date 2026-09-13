"""Shared contract suite: any SecurityAnalysisProvider (FakeSecurityAnalysisProvider today; a real
vendor adapter later) must satisfy this. Mirrors market_data_provider_suite.py's pattern -- import
these functions from a per-adapter test module rather than parametrizing here.
"""

from wallybot.domain.token_risk import SecurityAnalysisProvider


async def assert_analyze_token_for_an_unknown_token_reports_nothing_checked(
    provider: SecurityAnalysisProvider, chain: str, token_id: str
) -> None:
    result = await provider.analyze_token(chain, token_id)
    assert result.token_id == token_id
    assert result.chain == chain
    assert result.mint_authority_active is None
    assert result.freeze_authority_active is None
    assert result.liquidity_locked is None
    assert result.buy_tax_pct is None
    assert result.sell_tax_pct is None
    assert result.is_honeypot is None
    assert result.malicious_labels is None


async def assert_analyze_token_returns_seeded_data_unchanged(
    provider: SecurityAnalysisProvider, chain: str, token_id: str
) -> None:
    first = await provider.analyze_token(chain, token_id)
    second = await provider.analyze_token(chain, token_id)
    assert first == second
