"""Turns a `Fill` (Phase 4 Slice 2) into a balanced `LedgerTransaction` (Slice 3) -- the mapping
Slice 3 explicitly deferred: "which accounts a given fill's cash/position/fee legs actually hit."

Per DATA.md: "A BTC/USD trade records balanced BTC entries and balanced USD entries with clearing
accounts; it never adds BTC units to USD units." Each fill produces exactly two currencies' worth
of balanced legs: the account's own cash/position moves, offset by a `CLEARING` account per
currency representing the exchange side of the trade. Fee is netted into the cash leg rather than
given its own leg -- `fills.fee` already records it for cost reporting (DATA.md's cost-analytics
section reads that column directly), so a separate ledger leg would be redundant bookkeeping this
slice has no real consumer for yet.
"""

from decimal import Decimal

from wallybot.domain.execution import Fill
from wallybot.domain.ledger import AccountPurpose, LedgerAccount, LedgerPosting, LedgerTransaction
from wallybot.domain.order import Side

_CLEARING_ACCOUNT_ID = "clearing"


def build_fill_ledger_transaction(fill: Fill, account_id: str) -> LedgerTransaction:
    if fill.fee_currency != fill.instrument.quote:
        raise ValueError(
            f"fee currency {fill.fee_currency!r} does not match quote currency "
            f"{fill.instrument.quote!r}; a non-quote fee currency needs its own ledger "
            "treatment, which this builder does not yet implement"
        )

    cash = LedgerAccount(
        account_id=account_id, currency=fill.instrument.quote, purpose=AccountPurpose.CASH
    )
    clearing_quote = LedgerAccount(
        account_id=_CLEARING_ACCOUNT_ID,
        currency=fill.instrument.quote,
        purpose=AccountPurpose.CLEARING,
    )
    position = LedgerAccount(
        account_id=account_id, currency=fill.instrument.base, purpose=AccountPurpose.POSITION
    )
    clearing_base = LedgerAccount(
        account_id=_CLEARING_ACCOUNT_ID,
        currency=fill.instrument.base,
        purpose=AccountPurpose.CLEARING,
    )

    notional: Decimal = fill.quantity * fill.price
    if fill.side is Side.BUY:
        # Cash leaves the account for the notional plus the fee; the position leg mirrors it.
        cash_amount = -(notional + fill.fee)
    else:
        # Cash arrives net of the fee.
        cash_amount = notional - fill.fee
    position_amount = fill.quantity if fill.side is Side.BUY else -fill.quantity

    return LedgerTransaction(
        transaction_id=f"ledger-{fill.fill_id}",
        account_id=account_id,
        reason="FILL",
        reference_id=fill.fill_id,
        postings=(
            LedgerPosting(account=cash, amount=cash_amount),
            LedgerPosting(account=clearing_quote, amount=-cash_amount),
            LedgerPosting(account=position, amount=position_amount),
            LedgerPosting(account=clearing_base, amount=-position_amount),
        ),
        recorded_at=fill.filled_at,
    )
