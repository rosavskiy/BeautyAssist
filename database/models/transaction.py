"""Transaction model - represents payment transactions."""
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class TransactionStatus(str, Enum):
    """Transaction status."""
    
    PENDING = "pending"  # Payment pending
    SUCCEEDED = "succeeded"  # Payment successful
    FAILED = "failed"  # Payment failed
    CANCELLED = "cancelled"  # Payment cancelled
    REFUNDED = "refunded"  # Payment refunded


class TransactionType(str, Enum):
    """Transaction type."""
    
    SUBSCRIPTION = "subscription"  # Subscription payment
    RENEWAL = "renewal"  # Auto-renewal payment
    UPGRADE = "upgrade"  # Plan upgrade
    REFUND = "refund"  # Refund transaction


class Transaction(Base):
    """Transaction model for payment history."""
    
    __tablename__ = "transactions"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Subscription relationship
    subscription_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Master relationship (for quick access)
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Transaction details
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: subscription, renewal, upgrade, refund"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TransactionStatus.PENDING.value,
        index=True,
        comment="Status: pending, succeeded, failed, cancelled, refunded"
    )
    
    # Amount
    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount in currency units")
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    
    # Payment provider
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Payment method: telegram_stars, yookassa, manual"
    )
    
    # Provider data
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Payment ID from provider (YooKassa, Telegram)"
    )
    provider_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Full payment data from provider"
    )
    
    # Error info
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metadata (renamed from metadata)"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When transaction was completed (succeeded/failed)"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, master_id={self.master_id}, "
            f"amount={self.amount}, status='{self.status}')>"
        )
    
    @property
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == TransactionStatus.SUCCEEDED.value
    
    @property
    def is_pending(self) -> bool:
        """Check if transaction is pending."""
        return self.status == TransactionStatus.PENDING.value
