from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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


class EntityRow(Base):
    """Persists `wallybot.domain.entity.Entity`'s mutable summary fields. Attributions live in
    `EntityAttributionRow`, append-only, never here."""

    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('PERSON', 'PUBLIC_FIGURE', 'POLITICIAN', 'FUND', 'COMPANY', "
            "'EXCHANGE', 'INSTITUTION', 'WHALE', 'TRADER', 'WALLET_CLUSTER', "
            "'ANONYMOUS_WALLET', 'DEVELOPER', 'MARKET_MAKER', 'PROTOCOL', 'ETF', "
            "'GOVERNMENT', 'CUSTOM')"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(24))
    aliases: Mapped[list] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    trust_score: Mapped[Decimal] = mapped_column(Numeric)
    risk_score: Mapped[Decimal] = mapped_column(Numeric)
    influence_weight: Mapped[Decimal] = mapped_column(Numeric)
    tags: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EntityAttributionRow(Base):
    """Persists one `wallybot.domain.entity.Attribution` for an `Entity`. `(entity_id, source,
    source_entity_id, observed_at)` is this table's dedup key -- re-saving the same claim never
    duplicates it."""

    __tablename__ = "entity_attributions"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "source",
            "source_entity_id",
            "observed_at",
            name="uq_entity_attributions_dedup",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    source: Mapped[str] = mapped_column(String(64))
    source_entity_id: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    evidence: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(16))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WalletRow(Base):
    """Persists `wallybot.domain.wallet.Wallet`'s mutable summary fields, keyed the same way the
    domain object identifies itself: `(chain, address)`."""

    __tablename__ = "wallets"
    __table_args__ = (CheckConstraint("monitoring_mode IN ('OBSERVE', 'AI_EVALUATED', 'MIRROR')"),)
    chain: Mapped[str] = mapped_column(String(32), primary_key=True)
    address: Mapped[str] = mapped_column(String(128), primary_key=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    alias: Mapped[str | None] = mapped_column(String(200))
    labels: Mapped[list] = mapped_column(JSONB)
    tags: Mapped[list] = mapped_column(JSONB)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    trust_score: Mapped[Decimal] = mapped_column(Numeric)
    risk_score: Mapped[Decimal] = mapped_column(Numeric)
    enabled: Mapped[bool] = mapped_column(Boolean)
    monitoring_mode: Mapped[str] = mapped_column(String(16))
    influence_weight: Mapped[Decimal] = mapped_column(Numeric)
    max_signal_weight: Mapped[Decimal] = mapped_column(Numeric)
    max_allocation: Mapped[Decimal | None] = mapped_column(Numeric)
    min_transaction_value: Mapped[Decimal] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WalletAttributionRow(Base):
    """Persists one `Attribution` for a `Wallet`. `(chain, address, source, source_entity_id,
    observed_at)` is this table's dedup key."""

    __tablename__ = "wallet_attributions"
    __table_args__ = (
        ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
        UniqueConstraint(
            "chain",
            "address",
            "source",
            "source_entity_id",
            "observed_at",
            name="uq_wallet_attributions_dedup",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(64))
    source_entity_id: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    evidence: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(16))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WalletClusterRow(Base):
    """Persists `wallybot.domain.wallet.WalletCluster`'s header. Members live in
    `WalletClusterMemberRow`."""

    __tablename__ = "wallet_clusters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WalletClusterMemberRow(Base):
    __tablename__ = "wallet_cluster_members"
    __table_args__ = (
        ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
    )
    cluster_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("wallet_clusters.id"), primary_key=True
    )
    chain: Mapped[str] = mapped_column(String(32), primary_key=True)
    address: Mapped[str] = mapped_column(String(128), primary_key=True)


class RelationshipRow(Base):
    """Persists `wallybot.domain.relationship.Relationship` -- one flat, generic edge (typed
    source/target node references) rather than a family of foreign-key columns per node kind, so
    it stores today's relational schema cleanly and would translate directly to a graph edge
    later without a data model change."""

    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("source_type IN ('WALLET', 'ENTITY', 'TOKEN', 'EVENT', 'TRANSACTION')"),
        CheckConstraint("target_type IN ('WALLET', 'ENTITY', 'TOKEN', 'EVENT', 'TRANSACTION')"),
        CheckConstraint(
            "relationship_type IN ('OWNS', 'CONTROLS', 'FUNDS', 'TRADED', 'TRANSFERRED_TO', "
            "'TRANSFERRED_FROM', 'DEPLOYED', 'HOLDS', 'INVESTED_IN', 'RELATED_TO', "
            "'DISCLOSED_TRADE', 'INSIDER_OF')"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(16), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    relationship_type: Mapped[str] = mapped_column(String(24))
    target_type: Mapped[str] = mapped_column(String(16), index=True)
    target_id: Mapped[str] = mapped_column(String(128), index=True)
    attribution_source: Mapped[str] = mapped_column(String(64))
    attribution_source_entity_id: Mapped[str | None] = mapped_column(String(100))
    attribution_confidence: Mapped[Decimal] = mapped_column(Numeric)
    attribution_evidence: Mapped[str] = mapped_column(Text)
    attribution_verification_status: Mapped[str] = mapped_column(String(16))
    attribution_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
