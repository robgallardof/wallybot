from datetime import UTC, datetime
from decimal import Decimal

from tests.contract.security_analysis_provider_suite import (
    assert_analyze_token_for_an_unknown_token_reports_nothing_checked,
    assert_analyze_token_returns_seeded_data_unchanged,
)
from wallybot.domain.token_risk import SecurityAnalysisResult
from wallybot.intelligence.fake import FakeSecurityAnalysisProvider

NOW = datetime(2026, 1, 1, tzinfo=UTC)


class FixedClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def make_result(chain: str = "solana", token_id: str = "BONK") -> SecurityAnalysisResult:
    return SecurityAnalysisResult(
        token_id=token_id,
        chain=chain,
        mint_authority_active=False,
        freeze_authority_active=False,
        liquidity_locked=True,
        buy_tax_pct=Decimal("2"),
        sell_tax_pct=Decimal("2"),
        is_honeypot=False,
        malicious_labels=(),
        source="fake-vendor",
        fetched_at=NOW,
    )


async def test_analyze_token_for_an_unknown_token_reports_nothing_checked() -> None:
    provider = FakeSecurityAnalysisProvider(clock=FixedClock(NOW))
    await assert_analyze_token_for_an_unknown_token_reports_nothing_checked(
        provider, "solana", "UNKNOWN"
    )


async def test_analyze_token_returns_seeded_data_unchanged() -> None:
    result = make_result()
    provider = FakeSecurityAnalysisProvider(clock=FixedClock(NOW), results={"solana:BONK": result})
    await assert_analyze_token_returns_seeded_data_unchanged(provider, "solana", "BONK")


async def test_seeded_result_is_returned_verbatim() -> None:
    result = make_result()
    provider = FakeSecurityAnalysisProvider(clock=FixedClock(NOW), results={"solana:BONK": result})
    fetched = await provider.analyze_token("solana", "BONK")
    assert fetched == result
