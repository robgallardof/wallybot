"""Smart Money clustering: detect when several independent tracked wallets converge on the same
token within a configurable time window, per ARCHITECTURE.md's "Multi-source intelligence and
Smart Money": "3 unrelated Smart Money wallets buy the same token within 30 minutes."

"Do not count multiple wallets controlled by the same entity as independent confirmations" is
enforced by collapsing wallets that share the same `entity_id` (from the Wallet Registry) into a
single independent participant before counting -- two wallets with no known entity link always
count as independent from each other; identity we have not proven common is never assumed common.

Like `wallybot/domain/smart_money.py`, this only evaluates what wallet-activity data can actually
support (wallet count/identities, total value, average entry price, the time window itself) and
explicitly lists the wider spec's other named dimensions (liquidity change, volume change, holder
change, price movement, market regime) as not evaluated in every signal's `reasons`, rather than
fabricating them.

Windowing is a single left-to-right sweep per (chain, token): the window anchored at each
not-yet-consumed event grows to include every later event of the same action within `window`; if
enough independent wallets appear, a signal fires and the sweep jumps past every event it used
(so one wallet's transaction is never claimed by two overlapping signals); otherwise the sweep
slides forward by one event and retries. This can miss a cluster that only forms by combining the
tail of one candidate window with events just past it, a known, documented simplification for a
first slice, not a claim of finding every cluster that ever existed in the data.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from wallybot.domain.validation import require_aware_datetime, require_unit_interval
from wallybot.domain.wallet_activity import OnChainActionType, WalletActivityEvent

MIN_INDEPENDENT_WALLETS = 3

UNEVALUATED_DIMENSIONS = (
    "liquidity_change",
    "volume_change",
    "holder_change",
    "price_movement",
    "market_regime",
)


@dataclass(frozen=True)
class SmartMoneyClusterSignal:
    token: str
    chain: str
    action: OnChainActionType
    window_start: datetime
    window_end: datetime
    wallet_ids: tuple[str, ...]
    independent_wallet_count: int
    total_value_usd: Decimal
    average_entry_price: Decimal
    independence_score: Decimal
    confidence: Decimal
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.token:
            raise ValueError("token is required")
        if not self.chain:
            raise ValueError("chain is required")
        if len(self.wallet_ids) < 2:
            raise ValueError("a cluster needs at least two wallets")
        if len(set(self.wallet_ids)) != len(self.wallet_ids):
            raise ValueError("wallet_ids must be unique")
        if self.independent_wallet_count < 1:
            raise ValueError("independent_wallet_count must be positive")
        if self.independent_wallet_count > len(self.wallet_ids):
            raise ValueError("independent_wallet_count cannot exceed the number of wallets")
        if self.window_end < self.window_start:
            raise ValueError("window_end cannot be before window_start")
        if self.total_value_usd <= 0:
            raise ValueError("total_value_usd must be positive")
        if self.average_entry_price <= 0:
            raise ValueError("average_entry_price must be positive")
        require_unit_interval(self.independence_score, "independence_score")
        require_unit_interval(self.confidence, "confidence")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        require_aware_datetime(self.window_start, "window_start")
        require_aware_datetime(self.window_end, "window_end")


def _independent_groups(
    wallet_ids: set[str], entity_by_wallet: Mapping[str, str | None]
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for wallet_id in wallet_ids:
        entity_id = entity_by_wallet.get(wallet_id)
        key = entity_id if entity_id is not None else f"__wallet__:{wallet_id}"
        groups.setdefault(key, []).append(wallet_id)
    return groups


def detect_smart_money_clusters(
    events_by_wallet: Mapping[str, list[WalletActivityEvent]],
    entity_by_wallet: Mapping[str, str | None],
    action: OnChainActionType,
    window: timedelta,
    min_independent_wallets: int = MIN_INDEPENDENT_WALLETS,
) -> tuple[SmartMoneyClusterSignal, ...]:
    if window <= timedelta(0):
        raise ValueError("window must be positive")
    if min_independent_wallets < 2:
        raise ValueError("min_independent_wallets must be at least 2")

    by_market: dict[tuple[str, str], list[tuple[WalletActivityEvent, str]]] = {}
    for wallet_id, events in events_by_wallet.items():
        for event in events:
            if event.action is action:
                by_market.setdefault((event.chain, event.token), []).append((event, wallet_id))

    signals: list[SmartMoneyClusterSignal] = []
    for (chain, token), items in by_market.items():
        ordered = sorted(items, key=lambda pair: pair[0].occurred_at)
        index = 0
        while index < len(ordered):
            window_start = ordered[index][0].occurred_at
            deadline = window_start + window
            group = []
            j = index
            while j < len(ordered) and ordered[j][0].occurred_at <= deadline:
                group.append(ordered[j])
                j += 1

            wallet_ids_in_group = {wallet_id for _, wallet_id in group}
            independent_groups = _independent_groups(wallet_ids_in_group, entity_by_wallet)
            independent_count = len(independent_groups)

            events_only = [event for event, _ in group]
            total_value = sum(
                (event.value_usd for event in events_only if event.value_usd is not None),
                Decimal(0),
            )
            priced = [event for event in events_only if event.price is not None]
            average_entry = (
                sum((event.price for event in priced), Decimal(0)) / len(priced)
                if priced
                else Decimal(0)
            )

            if (
                independent_count >= min_independent_wallets
                and total_value > 0
                and average_entry > 0
            ):
                independence_score = Decimal(independent_count) / Decimal(len(wallet_ids_in_group))
                confidence = min(
                    Decimal(independent_count) / Decimal(min_independent_wallets * 2), Decimal(1)
                )
                signals.append(
                    SmartMoneyClusterSignal(
                        token=token,
                        chain=chain,
                        action=action,
                        window_start=window_start,
                        window_end=max(event.occurred_at for event in events_only),
                        wallet_ids=tuple(sorted(wallet_ids_in_group)),
                        independent_wallet_count=independent_count,
                        total_value_usd=total_value,
                        average_entry_price=average_entry,
                        independence_score=independence_score,
                        confidence=confidence,
                        reasons=(
                            f"{independent_count} independent wallet(s) {action.value} {token} "
                            f"within {window}",
                            f"not evaluated: {', '.join(UNEVALUATED_DIMENSIONS)}",
                        ),
                    )
                )
                index = j
            else:
                index += 1

    return tuple(signals)
