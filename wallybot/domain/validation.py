"""Small validation helpers shared across domain value types that would otherwise repeat the
same aware-datetime and unit-interval checks (`wallybot/domain/entity.py`, `wallet.py`, and any
later intelligence value type with a confidence/score field). Pure domain: no framework imports.
"""

from datetime import datetime
from decimal import Decimal


def require_aware_datetime(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError(f"{field} must be an aware datetime")


def require_unit_interval(value: Decimal, field: str) -> None:
    if not (Decimal(0) <= value <= Decimal(1)):
        raise ValueError(f"{field} must be between 0 and 1")
