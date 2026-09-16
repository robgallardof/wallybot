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
        CheckConstraint("environment IN ('OBSERVE', 'PAPER')"),
        CheckConstraint("status IN ('RUNNING', 'PAUSED')"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    environment: Mapped[str] = mapped_column(String(16), default="OBSERVE")
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
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    claimed_at: Mapped[int | None] = mapped_column(BigInteger)
    completed_at: Mapped[int | None] = mapped_column(BigInteger)
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)


class ProviderConnectionRow(Base):
    """A user-owned connection descriptor. Credentials remain outside this table."""

    __tablename__ = "provider_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "label", name="uq_provider_connections_owner"),
        CheckConstraint("mode IN ('READ_ONLY', 'PAPER', 'TRADE_ONLY')"),
        CheckConstraint("status IN ('PENDING', 'HEALTHY', 'UNAVAILABLE')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    created_at: Mapped[int] = mapped_column(BigInteger)


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


class WalletActivityEventRow(Base):
    """Persists `wallybot.domain.wallet_activity.WalletActivityEvent`. `(chain, address,
    transaction_hash, token, action)` is this table's dedup key -- a monitoring sync that re-fetches
    overlapping history must not duplicate an event it already ingested."""

    __tablename__ = "wallet_activity_events"
    __table_args__ = (
        ForeignKeyConstraint(["chain", "address"], ["wallets.chain", "wallets.address"]),
        UniqueConstraint(
            "chain",
            "address",
            "transaction_hash",
            "token",
            "action",
            name="uq_wallet_activity_events_dedup",
        ),
        CheckConstraint(
            "action IN ('BUY', 'SELL', 'SWAP', 'TRANSFER', 'MINT', 'BURN', 'ADD_LIQUIDITY', "
            "'REMOVE_LIQUIDITY', 'APPROVE', 'STAKE', 'UNSTAKE', 'BRIDGE')"
        ),
        CheckConstraint("amount > 0"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    address: Mapped[str] = mapped_column(String(128), index=True)
    transaction_hash: Mapped[str] = mapped_column(String(128))
    token: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric)
    value_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    price: Mapped[Decimal | None] = mapped_column(Numeric)
    liquidity_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attribution_source: Mapped[str] = mapped_column(String(64))
    attribution_source_entity_id: Mapped[str | None] = mapped_column(String(100))
    attribution_confidence: Mapped[Decimal] = mapped_column(Numeric)
    attribution_evidence: Mapped[str] = mapped_column(Text)
    attribution_verification_status: Mapped[str] = mapped_column(String(16))
    attribution_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SmartMoneyScoreSnapshotRow(Base):
    """Persists `wallybot.domain.smart_money.SmartMoneyScoreSnapshot`. Insert-only -- "store the
    score history... never overwrite previous score snapshots" (ARCHITECTURE.md). There is
    deliberately no unique constraint that would prevent two snapshots for the same wallet: a
    fresh evaluation is always a new row, timestamped by `computed_at`, never an update."""

    __tablename__ = "smart_money_score_snapshots"
    __table_args__ = (CheckConstraint("status IN ('SCORED', 'INSUFFICIENT_DATA')"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    trade_count: Mapped[int] = mapped_column(Integer)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    realized_pnl_usd: Mapped[Decimal | None] = mapped_column(Numeric)
    wallet_age_seconds: Mapped[Decimal | None] = mapped_column(Numeric)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons: Mapped[list] = mapped_column(JSONB)


class SmartMoneyClusterSignalRow(Base):
    """Persists `wallybot.domain.smart_money_cluster.SmartMoneyClusterSignal`. Insert-only, same
    reasoning as `SmartMoneyScoreSnapshotRow`: each detection run's output is a new fact about a
    moment in time, never a correction of an earlier one."""

    __tablename__ = "smart_money_cluster_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), index=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(24))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    wallet_ids: Mapped[list] = mapped_column(JSONB)
    independent_wallet_count: Mapped[int] = mapped_column(Integer)
    total_value_usd: Mapped[Decimal] = mapped_column(Numeric)
    average_entry_price: Mapped[Decimal] = mapped_column(Numeric)
    independence_score: Mapped[Decimal] = mapped_column(Numeric)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    reasons: Mapped[list] = mapped_column(JSONB)


class TokenRiskScoreRow(Base):
    """Persists `wallybot.domain.token_risk.TokenRiskScore`. Insert-only, same reasoning as
    `SmartMoneyScoreSnapshotRow`: a fresh evaluation is always a new row, never an update -- a
    token's risk profile can change (authority revoked, liquidity unlocked, a new malicious
    label), and history should show that rather than overwrite it."""

    __tablename__ = "token_risk_scores"
    __table_args__ = (CheckConstraint("status IN ('SCORED', 'INSUFFICIENT_DATA')"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_id: Mapped[str] = mapped_column(String(128), index=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric)
    reasons: Mapped[list] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WhaleTransferSignalRow(Base):
    """Persists `wallybot.domain.whale_flow.WhaleTransferSignal`. Insert-only: each detected
    transfer is its own fact, never updated or deduplicated at this layer -- the same reasoning as
    `SmartMoneyClusterSignalRow`."""

    __tablename__ = "whale_transfer_signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[str] = mapped_column(String(128), index=True)
    chain: Mapped[str] = mapped_column(String(32), index=True)
    token: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(24))
    amount: Mapped[Decimal] = mapped_column(Numeric)
    value_usd: Mapped[Decimal] = mapped_column(Numeric)
    threshold_usd: Mapped[Decimal] = mapped_column(Numeric)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons: Mapped[list] = mapped_column(JSONB)


class ProviderReliabilitySnapshotRow(Base):
    """Persists `wallybot.domain.provider_reliability.ProviderReliabilitySnapshot`. Insert-only:
    a provider's reliability changes over time, and history should show that, same reasoning as
    every other score/signal snapshot table in this schema."""

    __tablename__ = "provider_reliability_snapshots"
    __table_args__ = (
        CheckConstraint("status IN ('HEALTHY', 'DEGRADED', 'UNRELIABLE', 'INSUFFICIENT_DATA')"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24))
    call_count: Mapped[int] = mapped_column(Integer)
    error_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    average_latency_ms: Mapped[Decimal | None] = mapped_column(Numeric)
    seconds_since_last_success: Mapped[Decimal | None] = mapped_column(Numeric)
    reasons: Mapped[list] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class PriceConsensusResultRow(Base):
    """Persists `wallybot.domain.price_consensus.PriceConsensusResult`. Insert-only, same
    reasoning as every other snapshot table -- each computation is a fact about a moment in time."""

    __tablename__ = "price_consensus_results"
    __table_args__ = (CheckConstraint("status IN ('CONSENSUS', 'INSUFFICIENT_DATA')"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24))
    consensus_price: Mapped[Decimal | None] = mapped_column(Numeric)
    included_sources: Mapped[list] = mapped_column(JSONB)
    excluded_sources: Mapped[list] = mapped_column(JSONB)
    reasons: Mapped[list] = mapped_column(JSONB)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


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


class TradeProposalRow(Base):
    """Persists `wallybot.domain.trade_proposal.TradeProposal`. Insert-only audit trail, same
    reasoning as every other snapshot table: a `TradeProposal` is a fact about what the AI
    concluded at a moment in time, never corrected in place -- ARCHITECTURE.md's "Every
    TradeProposal ... must be as auditable as an approved one." `proposal_id` is the primary key
    rather than an autoincrement id: it is generated once per analysis and is never reused, so it
    is both identity and the natural idempotent insert key."""

    __tablename__ = "trade_proposals"
    __table_args__ = (CheckConstraint("direction IN ('LONG', 'SHORT')"),)
    proposal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    venue: Mapped[str] = mapped_column(String(32))
    base: Mapped[str] = mapped_column(String(16))
    quote: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    strategy_id: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric)
    suggested_allocation_pct: Mapped[Decimal] = mapped_column(Numeric)
    entry_price: Mapped[Decimal] = mapped_column(Numeric)
    stop_price: Mapped[Decimal | None] = mapped_column(Numeric)
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric)
    time_horizon_seconds: Mapped[Decimal] = mapped_column(Numeric)
    signal_ttl_seconds: Mapped[Decimal] = mapped_column(Numeric)
    reasons: Mapped[list] = mapped_column(JSONB)
    risks: Mapped[list] = mapped_column(JSONB)
    supporting_signal_ids: Mapped[list] = mapped_column(JSONB)
    invalidating_conditions: Mapped[list] = mapped_column(JSONB)
    source_event_ids: Mapped[list] = mapped_column(JSONB)
    model_id: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ShadowDecisionRow(Base):
    """Persists `wallybot.application.shadow_decision_service.ShadowDecisionOutcome`.
    Insert-only audit trail, same reasoning as `TradeProposalRow`: what the allocator/risk gate
    would have decided for an AI proposal is a fact about a moment in time, never corrected in
    place. No foreign key to `trade_proposals` -- an outcome is recorded whenever this service
    runs, independent of whether/when the proposal that produced it was itself persisted."""

    __tablename__ = "shadow_decisions"
    __table_args__ = (
        CheckConstraint(
            "risk_decision IS NULL OR "
            "risk_decision IN ('APPROVED', 'REJECTED', 'APPROVED_WITH_REDUCED_SIZE')"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proposal_id: Mapped[str] = mapped_column(String(64), index=True)
    venue: Mapped[str] = mapped_column(String(32))
    base: Mapped[str] = mapped_column(String(16))
    quote: Mapped[str] = mapped_column(String(16))
    allocation_approved: Mapped[bool] = mapped_column(Boolean)
    allocation_reasons: Mapped[list] = mapped_column(JSONB)
    risk_decision: Mapped[str | None] = mapped_column(String(32))
    risk_final_notional: Mapped[Decimal | None] = mapped_column(Numeric)
    risk_final_quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    risk_reasons: Mapped[list | None] = mapped_column(JSONB)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class HistoricalIngestionCursorRow(Base):
    """Tracks the last successfully ingested candle `close_time` per (instrument, timeframe), so
    a periodic re-fetch of an overlapping window never re-writes a Parquet partition
    `HistoricalStore` already published -- see `wallybot.application.market_ingestion`."""

    __tablename__ = "historical_ingestion_cursors"
    instrument_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExperimentRecordRow(Base):
    """Persists `wallybot.domain.experiment.ExperimentRecord`. Insert-only: an experiment is a
    fact about a run that happened, never corrected in place -- re-running with the same
    configuration produces a new record to compare against the old one, not an overwrite. Unlike
    `TradeProposalRow`, this table stores no `Instrument`-shaped object at all -- only plain
    venue/base/quote identity strings a caller already has -- so it fully round-trips without any
    fabrication concern."""

    __tablename__ = "experiment_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    strategy_id: Mapped[str] = mapped_column(String(64), index=True)
    strategy_version: Mapped[int] = mapped_column(Integer)
    feature_engine_version: Mapped[int] = mapped_column(Integer)
    backtest_engine_version: Mapped[int] = mapped_column(Integer)
    instrument_venue: Mapped[str] = mapped_column(String(32))
    instrument_base: Mapped[str] = mapped_column(String(16))
    instrument_quote: Mapped[str] = mapped_column(String(16))
    timeframe: Mapped[str] = mapped_column(String(16))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    feature_window: Mapped[int] = mapped_column(Integer)
    risk_off_threshold: Mapped[Decimal] = mapped_column(Numeric)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric)
    slippage_pct: Mapped[Decimal] = mapped_column(Numeric)
    starting_equity: Mapped[Decimal] = mapped_column(Numeric)
    allocation_pct: Mapped[Decimal] = mapped_column(Numeric)
    seed: Mapped[int | None] = mapped_column(BigInteger)
    trade_count: Mapped[int] = mapped_column(Integer)
    final_equity: Mapped[Decimal] = mapped_column(Numeric)
    total_return_pct: Mapped[Decimal] = mapped_column(Numeric)
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Numeric)
    win_rate: Mapped[Decimal | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
