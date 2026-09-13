"""Ledger value types: balanced double-entry postings, per DATA.md's "Enforce debit/credit
equality per asset/currency within a journal transaction at commit, not just through application
conventions" and "it never adds BTC units to USD units."

A posting's `amount` is signed (positive increases the account's balance, negative decreases it).
A `LedgerTransaction` is balanced when, for every currency its postings touch, those signed
amounts sum to exactly zero -- that is debit/credit equality expressed without needing separate
debit/credit fields. Grouping by currency before summing is what "never mix units" means in code:
a BTC posting can never cancel out a USD posting.

Pure domain: no framework imports, no persistence. `wallybot/infrastructure/` will give
`LedgerTransaction` a home in Postgres in a later slice; this module only guarantees that whatever
gets persisted was never unbalanced or unit-mixed in the first place.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class AccountPurpose(StrEnum):
    CASH = "CASH"
    POSITION = "POSITION"
    CLEARING = "CLEARING"
    FEE = "FEE"


@dataclass(frozen=True)
class LedgerAccount:
    account_id: str
    currency: str
    purpose: AccountPurpose

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("account_id is required")
        if not self.currency:
            raise ValueError("currency is required")


@dataclass(frozen=True)
class LedgerPosting:
    account: LedgerAccount
    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount == 0:
            raise ValueError("a posting with a zero amount carries no information; omit it")
        if not self.amount.is_finite():
            raise ValueError("amount must be finite")


@dataclass(frozen=True)
class LedgerTransaction:
    transaction_id: str
    account_id: str
    reason: str
    reference_id: str
    postings: tuple[LedgerPosting, ...]
    recorded_at: datetime

    def __post_init__(self) -> None:
        for name, value in (
            ("transaction_id", self.transaction_id),
            ("account_id", self.account_id),
            ("reason", self.reason),
            ("reference_id", self.reference_id),
        ):
            if not value:
                raise ValueError(f"{name} is required")
        if len(self.postings) < 2:
            raise ValueError("a transaction needs at least two postings to be double-entry")
        if (
            self.recorded_at.tzinfo is None
            or self.recorded_at.tzinfo.utcoffset(self.recorded_at) is None
        ):
            raise ValueError("recorded_at must be an aware datetime")

        by_currency: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for posting in self.postings:
            by_currency[posting.account.currency] += posting.amount
        unbalanced = {currency: total for currency, total in by_currency.items() if total != 0}
        if unbalanced:
            raise ValueError(f"transaction is not balanced per currency: {unbalanced}")
