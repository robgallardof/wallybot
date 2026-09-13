from datetime import UTC, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wallybot.domain.ledger import AccountPurpose, LedgerAccount, LedgerPosting, LedgerTransaction

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CURRENCIES = ("USD", "BTC", "ETH")


def _account(currency: str) -> LedgerAccount:
    return LedgerAccount(account_id="acct-1", currency=currency, purpose=AccountPurpose.CASH)


def _legs_per_currency() -> st.SearchStrategy[list[list[Decimal]]]:
    amount = st.decimals(
        min_value="0.01", max_value="1000", places=2, allow_nan=False, allow_infinity=False
    )
    return st.lists(st.lists(amount, min_size=2, max_size=3), min_size=1, max_size=len(CURRENCIES))


def _balanced_postings(
    legs_per_currency: list[list[Decimal]], data: st.DataObject
) -> list[LedgerPosting]:
    postings: list[LedgerPosting] = []
    for index, legs in enumerate(legs_per_currency):
        account = _account(CURRENCIES[index])
        signed = [leg if data.draw(st.booleans()) else -leg for leg in legs]
        balancing_leg = -sum(signed, Decimal(0))
        if balancing_leg == 0:
            # Add one more offsetting pair rather than mutate an existing leg, so no leg the
            # test constructs is ever a zero amount (LedgerPosting itself forbids that).
            signed.append(Decimal("0.01"))
            balancing_leg = Decimal("-0.01")
        for amount in [*signed, balancing_leg]:
            postings.append(LedgerPosting(account=account, amount=amount))
    return postings


@given(legs_per_currency=_legs_per_currency(), data=st.data())
def test_a_transaction_balanced_per_currency_always_validates(legs_per_currency, data) -> None:
    postings = _balanced_postings(legs_per_currency, data)
    transaction = LedgerTransaction(
        transaction_id="tx",
        account_id="acct-1",
        reason="TEST",
        reference_id="ref",
        postings=tuple(postings),
        recorded_at=NOW,
    )
    totals: dict[str, Decimal] = {}
    for posting in transaction.postings:
        totals[posting.account.currency] = (
            totals.get(posting.account.currency, Decimal(0)) + posting.amount
        )
    assert all(total == 0 for total in totals.values())


@given(
    legs_per_currency=_legs_per_currency(),
    data=st.data(),
    nudge=st.decimals(
        min_value="0.01", max_value="5", places=2, allow_nan=False, allow_infinity=False
    ),
)
def test_nudging_any_single_currency_off_balance_always_fails(
    legs_per_currency, data, nudge
) -> None:
    postings = _balanced_postings(legs_per_currency, data)
    target_index = data.draw(st.integers(min_value=0, max_value=len(legs_per_currency) - 1))
    target_currency = CURRENCIES[target_index]

    # Add one extra, unbalanced leg to the target currency rather than mutating an existing one
    # -- mutating risks the nudge exactly cancelling an existing leg back to a forbidden zero.
    extra = LedgerPosting(account=_account(target_currency), amount=nudge)
    nudged = [*postings, extra]

    with pytest.raises(ValueError, match="not balanced"):
        LedgerTransaction(
            transaction_id="tx",
            account_id="acct-1",
            reason="TEST",
            reference_id="ref",
            postings=tuple(nudged),
            recorded_at=NOW,
        )
