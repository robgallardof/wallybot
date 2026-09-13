"""Smart Money scoring, per ARCHITECTURE.md's "Multi-source intelligence and Smart Money":
"Never classify a wallet as Smart Money merely because it had one profitable trade."

Computes a bounded score only from what `WalletActivityEvent` data can actually support:
realized PnL from FIFO-matched BUY/SELL pairs -- DATA.md's own "documented FIFO lot convention
initially for realized PnL," reused here rather than invented fresh -- plus win rate, completed
trade count and wallet age. Every other dimension the wider spec names (unrealized PnL, drawdown,
a Sharpe-like risk adjustment, token quality, liquidity/entry/exit timing, rug/scam/wash-trading
exposure, portfolio concentration, market-regime performance) is explicitly NOT computed: this
codebase has no data source for any of them yet, and a formula that silently ignored them while
still producing a confident-looking 0-100 number would misrepresent what was actually evaluated.
Every `SmartMoneyScoreSnapshot` lists them, by name, as not evaluated.

A wallet with fewer than `MIN_COMPLETED_TRADES` realized round trips gets `INSUFFICIENT_DATA`,
never a score computed from noise -- this is the structural enforcement of "never ... merely
because it had one profitable trade."

The scoring weights below (60/40 split between win rate and realized PnL, the $1,000 PnL
normalization) are a versioned placeholder, not a claim of predictive validity or a backtested
calibration -- nothing in this codebase yet consumes a SmartMoneyScore for any financial decision
(it is Phase 10/11's OBSERVE-only research signal), and RISK.md's "do not invent universally safe
market thresholds" rule applies in full force the moment anything downstream tries to act on this
score, not just to risk limits themselves.

Pure domain: no framework imports, no persistence, no provider I/O.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.validation import require_aware_datetime
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

SMART_MONEY_SCORE_VERSION = 1
MIN_COMPLETED_TRADES = 5

UNSCORED_DIMENSIONS = (
    "unrealized_pnl",
    "drawdown",
    "sharpe_like_risk_adjustment",
    "token_quality",
    "liquidity_at_entry",
    "liquidity_at_exit",
    "entry_timing",
    "exit_timing",
    "rug_exposure",
    "scam_exposure",
    "wash_trading_indicators",
    "portfolio_concentration",
    "market_regime_performance",
)


class SmartMoneyStatus(StrEnum):
    SCORED = "SCORED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class CompletedTrade:
    token: str
    quantity: Decimal
    entry_price: Decimal
    exit_price: Decimal
    entry_at: datetime
    exit_at: datetime

    @property
    def realized_pnl_usd(self) -> Decimal:
        return (self.exit_price - self.entry_price) * self.quantity

    @property
    def holding_period(self) -> timedelta:
        return self.exit_at - self.entry_at


@dataclass(frozen=True)
class SmartMoneyScoreSnapshot:
    """One point-in-time score. Snapshots are never overwritten -- per ARCHITECTURE.md, "store
    the score history" -- a new evaluation always produces a new snapshot, never mutates an old
    one, regardless of how this type is persisted."""

    wallet_id: str
    version: int
    status: SmartMoneyStatus
    score: Decimal | None
    trade_count: int
    win_rate: Decimal | None
    realized_pnl_usd: Decimal | None
    wallet_age: timedelta | None
    computed_at: datetime
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.wallet_id:
            raise ValueError("wallet_id is required")
        if self.version < 1:
            raise ValueError("version must be positive")
        if self.trade_count < 0:
            raise ValueError("trade_count cannot be negative")
        if self.status is SmartMoneyStatus.SCORED:
            if self.score is None or not (Decimal(0) <= self.score <= Decimal(100)):
                raise ValueError("a SCORED snapshot must have a score between 0 and 100")
        elif self.score is not None:
            raise ValueError("an INSUFFICIENT_DATA snapshot must not carry a score")
        if self.win_rate is not None and not (Decimal(0) <= self.win_rate <= Decimal(1)):
            raise ValueError("win_rate must be between 0 and 1 when present")
        if not self.reasons:
            raise ValueError("reasons must not be empty -- every score needs evidence")
        require_aware_datetime(self.computed_at, "computed_at")


def _match_fifo_trades(events: list[WalletActivityEvent]) -> list[CompletedTrade]:
    """DATA.md's "documented FIFO lot convention initially for realized PnL," applied to on-chain
    activity: the earliest open BUY lot for a token is the one a later SELL closes against first.
    Events with no price (nothing this scorer can compute PnL from) are ignored, not guessed at.
    """
    ordered = sorted(events, key=lambda event: event.occurred_at)
    open_lots: dict[str, list[list]] = {}
    completed: list[CompletedTrade] = []
    for event in ordered:
        if event.price is None:
            continue
        if event.action is OnChainActionType.BUY:
            open_lots.setdefault(event.token, []).append(
                [event.amount, event.price, event.occurred_at]
            )
        elif event.action is OnChainActionType.SELL:
            lots = open_lots.get(event.token, [])
            remaining = event.amount
            while remaining > 0 and lots:
                lot = lots[0]
                matched = min(lot[0], remaining)
                completed.append(
                    CompletedTrade(
                        token=event.token,
                        quantity=matched,
                        entry_price=lot[1],
                        exit_price=event.price,
                        entry_at=lot[2],
                        exit_at=event.occurred_at,
                    )
                )
                lot[0] -= matched
                remaining -= matched
                if lot[0] <= 0:
                    lots.pop(0)
    return completed


def score_smart_money(
    wallet_id: str, events: list[WalletActivityEvent], now: datetime
) -> SmartMoneyScoreSnapshot:
    trades = _match_fifo_trades(events)
    reasons_unscored = f"not evaluated: {', '.join(UNSCORED_DIMENSIONS)}"

    if len(trades) < MIN_COMPLETED_TRADES:
        return SmartMoneyScoreSnapshot(
            wallet_id=wallet_id,
            version=SMART_MONEY_SCORE_VERSION,
            status=SmartMoneyStatus.INSUFFICIENT_DATA,
            score=None,
            trade_count=len(trades),
            win_rate=None,
            realized_pnl_usd=None,
            wallet_age=None,
            computed_at=now,
            reasons=(
                f"only {len(trades)} completed round trip(s), need at least {MIN_COMPLETED_TRADES}",
            ),
        )

    wins = sum(1 for trade in trades if trade.realized_pnl_usd > 0)
    win_rate = Decimal(wins) / Decimal(len(trades))
    realized_pnl = sum((trade.realized_pnl_usd for trade in trades), Decimal(0))
    occurred_ats = [event.occurred_at for event in events]
    wallet_age = max(occurred_ats) - min(occurred_ats)

    win_component = win_rate * Decimal(60)
    pnl_component = min(max(realized_pnl, Decimal(0)) / Decimal(1000), Decimal(1)) * Decimal(40)
    score = min(win_component + pnl_component, Decimal(100))

    return SmartMoneyScoreSnapshot(
        wallet_id=wallet_id,
        version=SMART_MONEY_SCORE_VERSION,
        status=SmartMoneyStatus.SCORED,
        score=score,
        trade_count=len(trades),
        win_rate=win_rate,
        realized_pnl_usd=realized_pnl,
        wallet_age=wallet_age,
        computed_at=now,
        reasons=(
            f"win_rate={win_rate}, realized_pnl_usd={realized_pnl} over {len(trades)} "
            "completed trades",
            reasons_unscored,
        ),
    )
