"""Explicit response DTOs for the API boundary.

Kept separate from `apps/api/schemas.py` (request/input DTOs) because input and output
validation change for different reasons: an input DTO tightens what a client may send, an
output DTO documents and locks the wire contract a client can rely on.
"""

from typing import Literal

from pydantic import BaseModel

from wallybot.domain.control import Status


class SetupStatusView(BaseModel):
    setup_required: bool


class SetupStartView(BaseModel):
    challenge: str
    secret: str
    uri: str


class SetupFinishView(BaseModel):
    recovery_codes: list[str]
    csrf: str


class ChallengeView(BaseModel):
    challenge: str


class CsrfView(BaseModel):
    csrf: str


class MeView(BaseModel):
    username: str
    role: Literal["ADMIN", "VIEWER"]
    csrf: str


class LogoutView(BaseModel):
    ok: bool


class DashboardView(BaseModel):
    environment: Literal["PAPER"]
    status: Status
    trading_available: Literal[False]
    exchange: str
    equity: None
    positions: list[object]
    phase: int


class ServiceStatusView(BaseModel):
    age_seconds: int | None
    status: str


class SystemView(BaseModel):
    api: str
    database: str
    redis: str
    services: dict[str, ServiceStatusView]
    exchange: str
    ai: str
    telegram: str
    live_available: Literal[False]


class EventView(BaseModel):
    id: str
    timestamp: int
    event: str
    message: str


class ControlView(BaseModel):
    status: Status
    environment: Literal["PAPER"]


class MarketRowView(BaseModel):
    id: str
    venue: str
    base: str
    quote: str
    bid: str
    ask: str
    spread_ratio: str
    quality_status: Literal["PASS", "WARNING", "FAILURE"]
    quality_reasons: list[str]
    eligible: bool
    rejection_reasons: list[str]
    score: str | None
    rank: int | None


class MarketsView(BaseModel):
    as_of: str
    rows: list[MarketRowView]


class SmartMoneyRowView(BaseModel):
    wallet_id: str
    status: Literal["SCORED", "INSUFFICIENT_DATA"]
    score: str | None
    trade_count: int
    win_rate: str | None
    realized_pnl_usd: str | None
    computed_at: str
    reasons: list[str]


class SmartMoneyView(BaseModel):
    rows: list[SmartMoneyRowView]


class WhaleTransferRowView(BaseModel):
    wallet_id: str
    chain: str
    token: str
    action: str
    amount: str
    value_usd: str
    threshold_usd: str
    occurred_at: str
    reasons: list[str]


class WhaleFlowView(BaseModel):
    rows: list[WhaleTransferRowView]


class TokenRiskRowView(BaseModel):
    token_id: str
    chain: str
    status: Literal["SCORED", "INSUFFICIENT_DATA"]
    risk_score: str | None
    computed_at: str
    reasons: list[str]


class TokenRiskView(BaseModel):
    rows: list[TokenRiskRowView]
