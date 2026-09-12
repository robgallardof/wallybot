from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, String, Text
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
