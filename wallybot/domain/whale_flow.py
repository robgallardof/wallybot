"""Whale intelligence: detect large on-chain transfers as signals, per ARCHITECTURE.md's "Whale
intelligence tracks large transfers and exchange/stablecoin flows as signals, not as an automatic
BUY/SELL interpretation -- the strategy/AI layer interprets them in context."

This slice delivers the "large transfer" half only. The wider spec also names exchange/stablecoin
flow direction (deposit-to-exchange vs. withdrawal-from-exchange) as a signal dimension, but
`wallybot.domain.wallet_activity.WalletActivityEvent` -- the only on-chain activity data source
this codebase has -- carries no counterparty/destination-wallet field at all (see its own
docstring: "amount is always positive; direction lives entirely in `action`", with no source/
destination wallet identity). Classifying a transfer as exchange-related needs that counterparty
identity cross-referenced against the Entity Registry's `EXCHANGE` entities -- a real data-model
gap, not something this slice can paper over. `UNEVALUATED_DIMENSIONS` names it explicitly rather
than guessing a direction with no data to support it. Extending `WalletActivityEvent` with a
counterparty field is real future work, flagged here, not done silently as part of this slice.

Every `WhaleTransferSignal` is a plain magnitude flag, deliberately not a trade interpretation --
"do not interpret a large transfer by itself as BUY or SELL," same rule `WalletActivityEvent`'s own
docstring already states for `action`, applied one level up.

Pure domain: no framework imports, no HTTP client, no provider SDK.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from wallybot.domain.validation import require_aware_datetime
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

UNEVALUATED_DIMENSIONS = (
    "exchange_flow_direction",
    "stablecoin_flow_classification",
)


@dataclass(frozen=True)
class WhaleTransferSignal:
    wallet_id: str
    chain: str
    token: str
    action: OnChainActionType
    amount: Decimal
    value_usd: Decimal
    threshold_usd: Decimal
    occurred_at: datetime
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        for field, value in (
            ("wallet_id", self.wallet_id),
            ("chain", self.chain),
            ("token", self.token),
        ):
            if not value:
                raise ValueError(f"{field} is required")
        if self.amount <= 0:
            raise ValueError("amount must be positive")
        if self.value_usd <= 0:
            raise ValueError("value_usd must be positive")
        if self.threshold_usd <= 0:
            raise ValueError("threshold_usd must be positive")
        if self.value_usd < self.threshold_usd:
            raise ValueError("value_usd must meet or exceed threshold_usd")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        require_aware_datetime(self.occurred_at, "occurred_at")


def detect_whale_transfers(
    events: Iterable[WalletActivityEvent], threshold_usd: Decimal
) -> tuple[WhaleTransferSignal, ...]:
    """Flag every event whose `value_usd` meets or exceeds `threshold_usd`. Events with no
    `value_usd` at all are skipped, never treated as zero -- an unpriced transfer's size is
    unknown, not small."""

    if threshold_usd <= 0:
        raise ValueError("threshold_usd must be positive")

    signals: list[WhaleTransferSignal] = []
    for event in events:
        if event.value_usd is None or event.value_usd < threshold_usd:
            continue
        signals.append(
            WhaleTransferSignal(
                wallet_id=event.wallet_id,
                chain=event.chain,
                token=event.token,
                action=event.action,
                amount=event.amount,
                value_usd=event.value_usd,
                threshold_usd=threshold_usd,
                occurred_at=event.occurred_at,
                reasons=(
                    f"{event.action.value} of {event.amount} {event.token} "
                    f"(${event.value_usd}) meets or exceeds the ${threshold_usd} whale threshold",
                    f"not evaluated: {', '.join(UNEVALUATED_DIMENSIONS)}",
                ),
            )
        )
    return tuple(signals)
