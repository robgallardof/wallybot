import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from wallybot.domain.ai_autonomy import AiAutonomyStatus
from wallybot.domain.control import Environment, Status


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.@+-]{3,100}", value):
            raise ValueError("Use 3–100 letters, digits or . _ @ + -")
        return value


class SetupStart(Login):
    bootstrap_token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class Verification(Input):
    challenge: str = Field(min_length=32, max_length=256)
    code: str = Field(min_length=6, max_length=128)


class SetupFinish(Verification):
    bootstrap_token: str = Field(min_length=32, max_length=256)


class MfaConfirm(Input):
    code: str = Field(min_length=6, max_length=6)


class PasswordChange(Input):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class ControlChange(Input):
    status: Status
    environment: Environment | None = None


class AiAutonomyChange(Input):
    status: AiAutonomyStatus
    target_core_pct: Decimal | None = Field(default=None, ge=0, le=1)
    target_growth_pct: Decimal | None = Field(default=None, ge=0, le=1)
    target_speculative_pct: Decimal | None = Field(default=None, ge=0, le=1)
    digest_interval_hours: int | None = Field(default=None, ge=1)
    codex_enabled: bool | None = None
    claude_enabled: bool | None = None
    require_consensus: bool | None = None


class BacktestRun(Input):
    instrument_base: str = Field(min_length=1, max_length=16)
    instrument_quote: str = Field(min_length=1, max_length=16)
    timeframe: Literal["1m", "5m", "1h", "1d"]
    window_start: datetime
    window_end: datetime
    feature_window: int = Field(ge=1, le=500)
    risk_off_threshold: Decimal = Field(gt=0)
    starting_equity: Decimal = Field(gt=0)
    allocation_pct: Decimal = Field(gt=0, le=1)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, le=1)
    slippage_pct: Decimal = Field(default=Decimal("0.0005"), ge=0, le=1)
    bootstrap_seed: int | None = None
    bootstrap_samples: int = Field(default=2000, ge=100, le=20000)
    walk_forward_windows: int | None = Field(default=None, ge=2, le=20)

    @field_validator("window_start", "window_end")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("must be an aware datetime")
        return value

    @field_validator("instrument_base", "instrument_quote")
    @classmethod
    def upper(cls, value: str) -> str:
        return value.strip().upper()


class ResearchJobCreate(Input):
    experiment_id: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=256)


class ProviderConnectionCreate(Input):
    provider: Literal["BINANCE", "BITSO", "KRAKEN", "COINBASE", "WALLET", "TIINGO"]
    label: str = Field(min_length=1, max_length=100)
    mode: Literal["READ_ONLY", "PAPER", "TRADE_ONLY"] = "READ_ONLY"
    # For an exchange: API key + secret (read-only/PAPER scope only -- never trade-only here).
    # For a wallet: only api_key is used, holding the public address.
    api_key: str | None = Field(default=None, max_length=4096)
    api_secret: str | None = Field(default=None, max_length=4096)

    @model_validator(mode="after")
    def supported_trading_connection(self) -> "ProviderConnectionCreate":
        if self.mode == "TRADE_ONLY" and (
            self.provider not in {"KRAKEN", "BINANCE"} or not self.api_key or not self.api_secret
        ):
            raise ValueError("Spot trading connections require a Kraken or Binance key and secret")
        return self


class ProviderConnectionUpdate(Input):
    label: str = Field(min_length=1, max_length=100)
    mode: Literal["READ_ONLY", "PAPER", "TRADE_ONLY"]
    # Omitted credentials keep the stored, encrypted ones.
    api_key: str | None = Field(default=None, max_length=4096)
    api_secret: str | None = Field(default=None, max_length=4096)


class TelegramConfigUpdate(Input):
    bot_token: str | None = Field(default=None, max_length=4096)
    chat_id: int | None = None
    enabled: bool = False
    # Generates a new one-time /start code without accepting a chat id from the browser.
    start_pairing: bool = False


class PortfolioFund(Input):
    amount: Decimal = Field(gt=0, le=Decimal("100000000"))
