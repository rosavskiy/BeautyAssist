"""PromoCode model - represents discount promo codes."""
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import BigInteger, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class PromoCodeType(str, Enum):
    """Promo code discount type."""
    
    PERCENT = "percent"  # Percentage discount (e.g., 20%)
    FIXED = "fixed"  # Fixed amount discount (e.g., 100 RUB)
    TRIAL_EXTENSION = "trial_extension"  # Extend trial period


class PromoCodeStatus(str, Enum):
    """Promo code status."""
    
    ACTIVE = "active"  # Active and can be used
    INACTIVE = "inactive"  # Temporarily disabled
    EXPIRED = "expired"  # Expired by date
    DEPLETED = "depleted"  # Usage limit reached


class PromoCode(Base):
    """Promo code model for discounts and promotions."""
    
    __tablename__ = "promo_codes"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Code
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Promo code (e.g., NEWYEAR2025)"
    )
    
    # Discount details
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: percent, fixed, trial_extension"
    )
    discount_percent: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Discount percentage (0-100) for percent type"
    )
    discount_amount: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Fixed discount amount for fixed type"
    )
    trial_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Additional trial days for trial_extension type"
    )
    
    # Validity
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PromoCodeStatus.ACTIVE.value,
        index=True,
        comment="Status: active, inactive, expired, depleted"
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now()
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiration date (null = no expiration)"
    )
    
    # Usage limits
    max_uses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum total uses (null = unlimited)"
    )
    max_uses_per_user: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Maximum uses per user"
    )
    current_uses: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Current usage count"
    )
    
    # Restrictions
    min_subscription_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum subscription duration required (e.g., only for yearly)"
    )
    
    # Referral
    is_referral: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Is this a referral code"
    )
    referrer_master_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Master who owns this referral code"
    )
    referrer_bonus_amount: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Bonus amount for referrer when code is used"
    )
    
    # Description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Internal description"
    )
    
    # Creator
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Admin telegram_id who created this code"
    )
    
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
        return f"<PromoCode(code='{self.code}', type='{self.type}', status='{self.status}')>"
    
    @property
    def is_valid(self) -> bool:
        """Check if promo code is currently valid."""
        if self.status != PromoCodeStatus.ACTIVE.value:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Check date validity
        if now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        
        # Check usage limit
        if self.max_uses and self.current_uses >= self.max_uses:
            return False
        
        return True
    
    @property
    def uses_remaining(self) -> int | None:
        """Calculate remaining uses (None if unlimited)."""
        if self.max_uses is None:
            return None
        return max(0, self.max_uses - self.current_uses)


class PromoCodeUsage(Base):
    """Track promo code usage history."""
    
    __tablename__ = "promo_code_usages"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Relationships
    promo_code_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("promo_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    subscription_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Discount applied
    discount_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Actual discount amount applied"
    )
    original_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Original price before discount"
    )
    final_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Final price after discount"
    )
    
    # Timestamp
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<PromoCodeUsage(promo_code_id={self.promo_code_id}, master_id={self.master_id})>"
