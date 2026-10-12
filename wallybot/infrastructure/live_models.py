"""Operator-selected real account and explicit execution limits. API-only access."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from wallybot.infrastructure.models import Base


class LiveControlRow(Base):
    __tablename__ = "live_control"
    __table_args__ = (
        CheckConstraint("id = 1"),
        CheckConstraint("max_order_usd > 0 AND max_daily_loss_usd > 0 AND max_total_usd > 0"),
        CheckConstraint("slippage_pct > 0 AND slippage_pct <= 0.02"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("provider_connections.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False)
    max_order_usd: Mapped[Decimal] = mapped_column(Numeric)
    max_daily_loss_usd: Mapped[Decimal] = mapped_column(Numeric)
    max_total_usd: Mapped[Decimal] = mapped_column(Numeric)
    slippage_pct: Mapped[Decimal] = mapped_column(Numeric)
    version: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(32), default="DISABLED")
    reason: Mapped[str] = mapped_column(String(256), default="")


class AnalystPortfolioRow(Base):
    """Sanitized read-only context; contains no keys, order IDs or execution authority."""

    __tablename__ = "analyst_portfolio_context"
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    cash_usd: Mapped[Decimal] = mapped_column(Numeric)
    holdings: Mapped[dict] = mapped_column(JSONB)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
