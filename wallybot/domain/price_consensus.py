"""Price consensus across independent feeds, per ARCHITECTURE.md: "where multiple independent
price feeds exist WallyBot computes a consensus price and rejects orders against a stale or
outlier quote."

Only one real market-data provider (Kraken) is wired up today, so nothing in this codebase yet
calls this with more than one genuinely independent quote -- this module defines the pure
computation any future multi-provider caller needs, tested against synthetic quotes, same as
`classify_regime`/`RiskEngine` were built as pure rules before every consumer existed.

A quote older than `max_staleness` is dropped before consensus is computed at all -- "reject a
stale quote" is enforced by exclusion, not a downstream flag a caller could ignore. A quote that
survives staleness filtering but deviates from the group median by more than
`outlier_threshold_pct` is excluded as an outlier and named in `reasons`, never silently averaged
in. Fewer than `MIN_QUOTES_FOR_CONSENSUS` quotes survive both filters yields `INSUFFICIENT_DATA`
rather than a "consensus" computed from a single, unconfirmed source.

Pure domain: no framework imports, no HTTP client.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from wallybot.domain.validation import require_aware_datetime

MIN_QUOTES_FOR_CONSENSUS = 2
DEFAULT_MAX_STALENESS = timedelta(minutes=5)
DEFAULT_OUTLIER_THRESHOLD_PCT = Decimal("0.02")


class PriceConsensusStatus(StrEnum):
    CONSENSUS = "CONSENSUS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class PriceQuote:
    source: str
    price: Decimal
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.source:
            raise ValueError("source is required")
        if self.price <= 0:
            raise ValueError("price must be positive")
        require_aware_datetime(self.observed_at, "observed_at")


@dataclass(frozen=True)
class PriceConsensusResult:
    instrument_id: str
    status: PriceConsensusStatus
    consensus_price: Decimal | None
    included_sources: tuple[str, ...]
    excluded_sources: tuple[str, ...]
    reasons: tuple[str, ...]
    computed_at: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id:
            raise ValueError("instrument_id is required")
        if self.status is PriceConsensusStatus.CONSENSUS:
            if self.consensus_price is None:
                raise ValueError("a CONSENSUS result must carry a consensus_price")
            if self.consensus_price <= 0:
                raise ValueError("consensus_price must be positive")
            if len(self.included_sources) < MIN_QUOTES_FOR_CONSENSUS:
                raise ValueError(
                    f"a CONSENSUS result needs at least {MIN_QUOTES_FOR_CONSENSUS} included sources"
                )
        elif self.consensus_price is not None:
            raise ValueError("an INSUFFICIENT_DATA result must not carry a consensus_price")
        if not self.reasons:
            raise ValueError("reasons must not be empty")
        require_aware_datetime(self.computed_at, "computed_at")


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    midpoint = count // 2
    if count % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)


def compute_price_consensus(
    instrument_id: str,
    quotes: Iterable[PriceQuote],
    now: datetime,
    max_staleness: timedelta = DEFAULT_MAX_STALENESS,
    outlier_threshold_pct: Decimal = DEFAULT_OUTLIER_THRESHOLD_PCT,
) -> PriceConsensusResult:
    if max_staleness <= timedelta(0):
        raise ValueError("max_staleness must be positive")
    if outlier_threshold_pct <= 0:
        raise ValueError("outlier_threshold_pct must be positive")

    all_quotes = list(quotes)
    fresh = [quote for quote in all_quotes if now - quote.observed_at <= max_staleness]
    stale = [quote for quote in all_quotes if quote not in fresh]

    if len(fresh) < MIN_QUOTES_FOR_CONSENSUS:
        return PriceConsensusResult(
            instrument_id=instrument_id,
            status=PriceConsensusStatus.INSUFFICIENT_DATA,
            consensus_price=None,
            included_sources=(),
            excluded_sources=tuple(quote.source for quote in all_quotes),
            reasons=(
                f"only {len(fresh)} fresh quote(s) within {max_staleness}, "
                f"need at least {MIN_QUOTES_FOR_CONSENSUS}",
            ),
            computed_at=now,
        )

    reference_price = _median([quote.price for quote in fresh])
    included: list[PriceQuote] = []
    outliers: list[PriceQuote] = []
    for quote in fresh:
        deviation = abs(quote.price - reference_price) / reference_price
        if deviation > outlier_threshold_pct:
            outliers.append(quote)
        else:
            included.append(quote)

    if len(included) < MIN_QUOTES_FOR_CONSENSUS:
        return PriceConsensusResult(
            instrument_id=instrument_id,
            status=PriceConsensusStatus.INSUFFICIENT_DATA,
            consensus_price=None,
            included_sources=(),
            excluded_sources=tuple(quote.source for quote in all_quotes),
            reasons=(
                f"only {len(included)} quote(s) survived outlier filtering, "
                f"need at least {MIN_QUOTES_FOR_CONSENSUS}",
            ),
            computed_at=now,
        )

    consensus_price = sum((quote.price for quote in included), Decimal(0)) / Decimal(len(included))
    excluded_sources = tuple(quote.source for quote in stale) + tuple(
        quote.source for quote in outliers
    )
    reasons = [
        f"{len(included)} of {len(all_quotes)} quote(s) included after staleness/outlier filtering"
    ]
    if stale:
        reasons.append(f"excluded as stale: {', '.join(quote.source for quote in stale)}")
    if outliers:
        reasons.append(f"excluded as outliers: {', '.join(quote.source for quote in outliers)}")

    return PriceConsensusResult(
        instrument_id=instrument_id,
        status=PriceConsensusStatus.CONSENSUS,
        consensus_price=consensus_price,
        included_sources=tuple(quote.source for quote in included),
        excluded_sources=excluded_sources,
        reasons=tuple(reasons),
        computed_at=now,
    )
