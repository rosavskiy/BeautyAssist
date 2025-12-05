"""Subscription model - represents master's subscription plan."""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class SubscriptionPlan(str, Enum):
    """Subscription plan types."""
    
    TRIAL = "trial"  # 14 days free trial
    MONTHLY = "monthly"  # Monthly subscription
    QUARTERLY = "quarterly"  # 3 months
    YEARLY = "yearly"  # 12 months (discount)


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    
    ACTIVE = "active"  # Active subscription
    EXPIRED = "expired"  # Expired subscription
    CANCELLED = "cancelled"  # Cancelled by user
    PENDING = "pending"  # Payment pending


class PaymentMethod(str, Enum):
    """Payment method types."""
    
    TELEGRAM_STARS = "telegram_stars"  # Telegram Stars
    YOOKASSA = "yookassa"  # YooKassa (cards, SBP, etc.)
    MANUAL = "manual"  # Manual activation by admin


class Subscription(Base):
    """Subscription model."""
    
    __tablename__ = "subscriptions"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Master relationship
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Subscription details
    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Subscription plan: trial, monthly, quarterly, yearly"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SubscriptionStatus.PENDING.value,
        index=True,
        comment="Status: active, expired, cancelled, pending"
    )
    
    # Dates
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Payment info
    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount in currency units")
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    payment_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment method: telegram_stars, yookassa, manual"
    )
    
    # Auto-renewal
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Cancellation
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return (
            f"<Subscription(id={self.id}, master_id={self.master_id}, "
            f"plan='{self.plan}', status='{self.status}')>"
        )
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return (
            self.status == SubscriptionStatus.ACTIVE.value
            and datetime.now(timezone.utc) < self.end_date
        )
    
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining until expiration."""
        if self.status != SubscriptionStatus.ACTIVE.value:
            return 0
        delta = self.end_date - datetime.now(timezone.utc)
        return max(0, delta.days)
