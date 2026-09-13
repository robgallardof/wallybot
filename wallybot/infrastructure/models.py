from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ControlRow(Base):
    __tablename__ = "control"
    __table_args__ = (
        CheckConstraint("id = 1"),
        CheckConstraint("environment = 'PAPER'"),
        CheckConstraint("status IN ('RUNNING', 'PAUSED')"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    environment: Mapped[str] = mapped_column(String(16), default="PAPER")
    status: Mapped[str] = mapped_column(String(16), default="RUNNING")


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('ADMIN', 'VIEWER')"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    totp_encrypted: Mapped[str] = mapped_column(Text)
    last_totp_step: Mapped[int] = mapped_column(BigInteger, default=-1)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[int] = mapped_column(BigInteger)


class ChallengeRow(Base):
    __tablename__ = "auth_challenges"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    username: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(Text)
    totp_encrypted: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    created_at: Mapped[int] = mapped_column(BigInteger)
    last_seen: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    mfa_at: Mapped[int] = mapped_column(BigInteger)


class RecoveryRow(Base):
    __tablename__ = "recovery_codes"
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[int] = mapped_column(BigInteger, index=True)
    actor: Mapped[str | None] = mapped_column(String(36))
    event: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(256))
    correlation_id: Mapped[str] = mapped_column(String(36))


class HeartbeatRow(Base):
    __tablename__ = "heartbeats"
    service: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[int] = mapped_column(BigInteger)


class JobRow(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    scheduled_at: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class OrderIntentRow(Base):
    """Persists `wallybot.domain.order.OrderIntent`. Uniqueness matches DATA.md exactly:
    "(account_id, environment, idempotency_key) identifies an intent.\""""

    __tablename__ = "order_intents"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "environment", "idempotency_key", name="uq_order_intents_idempotency"
        ),
        CheckConstraint("environment IN ('PAPER', 'LIVE')"),
        CheckConstraint("side IN ('BUY', 'SELL')"),
        CheckConstraint("kind IN ('MARKET', 'LIMIT')"),
        CheckConstraint("quantity > 0"),
    )
    client_order_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    environment: Mapped[str] = mapped_column(String(8))
    venue: Mapped[str] = mapped_column(String(32))
    base: Mapped[str] = mapped_column(String(16))
    quote: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    limit_price: Mapped[Decimal | None] = mapped_column(Numeric)
    decision_id: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    risk_assessment_id: Mapped[str] = mapped_column(String(64))
    config_versions: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24))


class OrderTransitionRow(Base):
    """Audit trail of `OrderStatus` transitions -- the durable record ADR-008 needs to persist
    SUBMITTING (and every other transition) before/after calling an exchange."""

    __tablename__ = "order_transitions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("order_intents.client_order_id"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FillRow(Base):
    """Persists `wallybot.domain.execution.Fill`. Uniqueness matches DATA.md's fill-dedup rule:
    "(venue, account_id, environment, exchange_fill_id).\""""

    __tablename__ = "fills"
    __table_args__ = (
        UniqueConstraint("venue", "account_id", "environment", "fill_id", name="uq_fills_dedup"),
        CheckConstraint("quantity > 0"),
        CheckConstraint("price > 0"),
        CheckConstraint("fee >= 0"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fill_id: Mapped[str] = mapped_column(String(100))
    client_order_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("order_intents.client_order_id"), index=True
    )
    account_id: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(8))
    venue: Mapped[str] = mapped_column(String(32))
    base: Mapped[str] = mapped_column(String(16))
    quote: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    price: Mapped[Decimal] = mapped_column(Numeric)
    fee: Mapped[Decimal] = mapped_column(Numeric)
    fee_currency: Mapped[str] = mapped_column(String(16))
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerAccountRow(Base):
    """Persists `wallybot.domain.ledger.LedgerAccount`."""

    __tablename__ = "ledger_accounts"
    __table_args__ = (
        UniqueConstraint("account_id", "currency", "purpose", name="uq_ledger_accounts"),
        CheckConstraint("purpose IN ('CASH', 'POSITION', 'CLEARING', 'FEE')"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    currency: Mapped[str] = mapped_column(String(16))
    purpose: Mapped[str] = mapped_column(String(16))


class LedgerTransactionRow(Base):
    """Persists a `wallybot.domain.ledger.LedgerTransaction` header. `(account_id, reference_id)`
    is this table's own dedup key, e.g. one transaction per fill_id -- posting the same fill
    twice must not double the ledger."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "reference_id", name="uq_ledger_transactions_dedup"),
    )
    transaction_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    reference_id: Mapped[str] = mapped_column(String(100))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LedgerPostingRow(Base):
    """Persists one `wallybot.domain.ledger.LedgerPosting` leg. Balance-per-currency is enforced
    by `LedgerTransaction.__post_init__` before anything reaches this table -- this row layer
    trusts an already-validated aggregate rather than re-deriving the invariant in SQL."""

    __tablename__ = "ledger_postings"
    __table_args__ = (CheckConstraint("amount <> 0"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("ledger_transactions.transaction_id"), index=True
    )
    ledger_account_id: Mapped[int] = mapped_column(Integer, ForeignKey("ledger_accounts.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric)
