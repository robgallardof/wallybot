"""Token intelligence: `SecurityAnalysisProvider` port and `TokenRiskScore`, per ARCHITECTURE.md's
Contracts table: "Token/contract safety checks (mint/freeze authority, liquidity locks, honeypot
indicators) feeding TokenRiskScore" and the "Token intelligence" section, which also names market
cap, FDV, liquidity, holder concentration, contract/pool/developer-wallet age, buy/sell tax and
known malicious labels as inputs.

No `SecurityAnalysisProvider` vendor (GoPlus, Honeypot.is, TokenSniffer, RugCheck, ...) has been
integrated yet -- the same "blocked on a real API key" situation as Phase 10 Slice 4b's wallet/
entity vendors. This module defines the port and a pure, honest scoring function that a caller can
drive with any provider's output. Holder concentration and contract/pool/developer-wallet age are
listed as `UNSCORED_DIMENSIONS`: no provider, real or planned, in this codebase supplies them yet,
so inventing a number for them would misrepresent what was actually evaluated. Market cap/FDV
(already real, via `wallybot.domain.market_metadata.TokenMarketMetadata`) are a separate concern
from contract/security safety and are not folded into this score -- they measure size, not safety.

Higher `risk_score` means riskier (0 = every checked dimension came back clean, 100 = a confirmed
critical risk such as a honeypot or a known-malicious label) -- the opposite polarity from Smart
Money's "higher is better" score, deliberately, since this number gates entry rather than ranks
quality. **The per-dimension point weights below are an explicitly-labeled versioned placeholder,
not a backtested calibration**, exactly like `smart_money.py`'s 60/40 split -- nothing downstream
consumes this score for any financial decision yet, and RISK.md's "do not invent universally safe
market thresholds" applies the moment anything ever does.

Pure domain: no framework imports, no HTTP client, no provider SDK.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from wallybot.domain.validation import require_aware_datetime

TOKEN_RISK_SCORE_VERSION = 1

UNSCORED_DIMENSIONS = (
    "holder_concentration",
    "contract_age",
    "pool_age",
    "developer_wallet_age",
)

_MINT_AUTHORITY_RISK = Decimal(25)
_FREEZE_AUTHORITY_RISK = Decimal(20)
_UNLOCKED_LIQUIDITY_RISK = Decimal(20)
_MAX_TAX_RISK = Decimal(15)
_CRITICAL_RISK = Decimal(100)


class TokenRiskStatus(StrEnum):
    SCORED = "SCORED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class SecurityAnalysisResult:
    """One provider's raw safety-check output for a single token/contract. Every field is `None`
    when the provider did not check or report it -- never a guessed default, matching
    `TokenMarketMetadata`'s own "field the provider did not return is None" convention."""

    token_id: str
    chain: str
    mint_authority_active: bool | None
    freeze_authority_active: bool | None
    liquidity_locked: bool | None
    buy_tax_pct: Decimal | None
    sell_tax_pct: Decimal | None
    is_honeypot: bool | None
    malicious_labels: tuple[str, ...] | None
    source: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        for field, value in (
            ("token_id", self.token_id),
            ("chain", self.chain),
            ("source", self.source),
        ):
            if not value:
                raise ValueError(f"{field} is required")
        for field, value in (
            ("buy_tax_pct", self.buy_tax_pct),
            ("sell_tax_pct", self.sell_tax_pct),
        ):
            if value is not None and not (Decimal(0) <= value <= Decimal(100)):
                raise ValueError(f"{field} must be between 0 and 100 when present")
        require_aware_datetime(self.fetched_at, "fetched_at")


class SecurityAnalysisProvider(Protocol):
    """Token/contract safety checks feeding `TokenRiskScore`, per ARCHITECTURE.md's Contracts
    table. Never a substitute for `MarketMetadataProvider`'s market-cap/supply data."""

    async def analyze_token(self, chain: str, token_id: str) -> SecurityAnalysisResult: ...


@dataclass(frozen=True)
class TokenRiskScore:
    token_id: str
    chain: str
    version: int
    status: TokenRiskStatus
    risk_score: Decimal | None
    reasons: tuple[str, ...]
    computed_at: datetime

    def __post_init__(self) -> None:
        if not self.token_id:
            raise ValueError("token_id is required")
        if not self.chain:
            raise ValueError("chain is required")
        if self.status is TokenRiskStatus.SCORED:
            if self.risk_score is None:
                raise ValueError("a SCORED score must carry a risk_score")
            if not (Decimal(0) <= self.risk_score <= Decimal(100)):
                raise ValueError("risk_score must be between 0 and 100")
        elif self.risk_score is not None:
            raise ValueError("an INSUFFICIENT_DATA score must not carry a risk_score")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        require_aware_datetime(self.computed_at, "computed_at")


def score_token_risk(result: SecurityAnalysisResult, now: datetime) -> TokenRiskScore:
    """Score only the dimensions `result` actually reports. A provider that reported nothing at
    all yields `INSUFFICIENT_DATA`, never a fabricated "looks safe" zero."""

    reasons: list[str] = []
    risk_points = Decimal(0)
    evaluated = False

    if result.mint_authority_active is not None:
        evaluated = True
        if result.mint_authority_active:
            risk_points += _MINT_AUTHORITY_RISK
            reasons.append("mint authority is still active")
        else:
            reasons.append("mint authority has been revoked")

    if result.freeze_authority_active is not None:
        evaluated = True
        if result.freeze_authority_active:
            risk_points += _FREEZE_AUTHORITY_RISK
            reasons.append("freeze authority is still active")
        else:
            reasons.append("freeze authority has been revoked")

    if result.liquidity_locked is not None:
        evaluated = True
        if result.liquidity_locked:
            reasons.append("liquidity is locked")
        else:
            risk_points += _UNLOCKED_LIQUIDITY_RISK
            reasons.append("liquidity is not locked")

    if result.buy_tax_pct is not None:
        evaluated = True
        risk_points += min(result.buy_tax_pct, _MAX_TAX_RISK)
        reasons.append(f"buy tax is {result.buy_tax_pct}%")

    if result.sell_tax_pct is not None:
        evaluated = True
        risk_points += min(result.sell_tax_pct, _MAX_TAX_RISK)
        reasons.append(f"sell tax is {result.sell_tax_pct}%")

    if result.is_honeypot is not None:
        evaluated = True
        if result.is_honeypot:
            risk_points = _CRITICAL_RISK
            reasons.append("honeypot detected: sells are blocked")
        else:
            reasons.append("no honeypot behavior detected")

    if result.malicious_labels is not None:
        evaluated = True
        if result.malicious_labels:
            risk_points = _CRITICAL_RISK
            reasons.append(f"known malicious label(s): {', '.join(result.malicious_labels)}")
        else:
            reasons.append("no known malicious labels")

    if not evaluated:
        return TokenRiskScore(
            token_id=result.token_id,
            chain=result.chain,
            version=TOKEN_RISK_SCORE_VERSION,
            status=TokenRiskStatus.INSUFFICIENT_DATA,
            risk_score=None,
            reasons=("the provider reported no security checks for this token",),
            computed_at=now,
        )

    reasons.append(f"not evaluated: {', '.join(UNSCORED_DIMENSIONS)}")
    return TokenRiskScore(
        token_id=result.token_id,
        chain=result.chain,
        version=TOKEN_RISK_SCORE_VERSION,
        status=TokenRiskStatus.SCORED,
        risk_score=min(risk_points, _CRITICAL_RISK),
        reasons=tuple(reasons),
        computed_at=now,
    )
