from datetime import UTC, datetime
from decimal import Decimal

import pytest

from wallybot.domain.ledger import AccountPurpose, LedgerAccount, LedgerPosting, LedgerTransaction

NOW = datetime(2026, 1, 1, tzinfo=UTC)
CASH = LedgerAccount(account_id="acct-1", currency="USD", purpose=AccountPurpose.CASH)
POSITION = LedgerAccount(account_id="acct-1", currency="BTC", purpose=AccountPurpose.POSITION)
CLEARING_USD = LedgerAccount(account_id="clearing", currency="USD", purpose=AccountPurpose.CLEARING)
CLEARING_BTC = LedgerAccount(account_id="clearing", currency="BTC", purpose=AccountPurpose.CLEARING)
FEE = LedgerAccount(account_id="fees", currency="USD", purpose=AccountPurpose.FEE)


def test_a_balanced_buy_transaction_is_accepted() -> None:
    transaction = LedgerTransaction(
        transaction_id="tx-1",
        account_id="acct-1",
        reason="FILL",
        reference_id="fill-1",
        postings=(
            LedgerPosting(account=CASH, amount=Decimal("-60000.06")),
            LedgerPosting(account=CLEARING_USD, amount=Decimal("60000.06")),
            LedgerPosting(account=POSITION, amount=Decimal("1")),
            LedgerPosting(account=CLEARING_BTC, amount=Decimal("-1")),
        ),
        recorded_at=NOW,
    )
    assert len(transaction.postings) == 4


def test_a_posting_that_leaves_its_currency_unbalanced_is_rejected() -> None:
    with pytest.raises(ValueError, match="not balanced"):
        LedgerTransaction(
            transaction_id="tx-2",
            account_id="acct-1",
            reason="FILL",
            reference_id="fill-2",
            postings=(
                LedgerPosting(account=CASH, amount=Decimal("-100")),
                LedgerPosting(account=CLEARING_USD, amount=Decimal("99")),
            ),
            recorded_at=NOW,
        )


def test_balancing_across_currencies_does_not_count_as_balanced() -> None:
    # A USD posting and a BTC posting of the "same" magnitude never cancel out -- units never mix.
    with pytest.raises(ValueError, match="not balanced"):
        LedgerTransaction(
            transaction_id="tx-3",
            account_id="acct-1",
            reason="FILL",
            reference_id="fill-3",
            postings=(
                LedgerPosting(account=CASH, amount=Decimal("-1")),
                LedgerPosting(account=POSITION, amount=Decimal("1")),
            ),
            recorded_at=NOW,
        )


def test_fee_leg_still_balances_when_included() -> None:
    transaction = LedgerTransaction(
        transaction_id="tx-4",
        account_id="acct-1",
        reason="FILL",
        reference_id="fill-4",
        postings=(
            LedgerPosting(account=CASH, amount=Decimal("-100.10")),
            LedgerPosting(account=FEE, amount=Decimal("0.10")),
            LedgerPosting(account=CLEARING_USD, amount=Decimal("100")),
        ),
        recorded_at=NOW,
    )
    assert len(transaction.postings) == 3


def test_zero_amount_posting_is_rejected() -> None:
    with pytest.raises(ValueError, match="zero amount"):
        LedgerPosting(account=CASH, amount=Decimal("0"))


def test_single_posting_is_rejected_as_not_double_entry() -> None:
    with pytest.raises(ValueError, match="at least two postings"):
        LedgerTransaction(
            transaction_id="tx-5",
            account_id="acct-1",
            reason="FILL",
            reference_id="fill-5",
            postings=(LedgerPosting(account=CASH, amount=Decimal("-1")),),
            recorded_at=NOW,
        )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="aware"):
        LedgerTransaction(
            transaction_id="tx-6",
            account_id="acct-1",
            reason="FILL",
            reference_id="fill-6",
            postings=(
                LedgerPosting(account=CASH, amount=Decimal("-1")),
                LedgerPosting(account=CLEARING_USD, amount=Decimal("1")),
            ),
            recorded_at=datetime(2026, 1, 1),
        )
