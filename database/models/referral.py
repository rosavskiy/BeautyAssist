"""Referral model for tracking referral program."""
from datetime import datetime
from typing import TYPE_CHECKING
from enum import Enum

from sqlalchemy import BigInteger, String, Boolean, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.master import Master


class ReferralStatus(str, Enum):
    """Referral status enum."""
    PENDING = "pending"  # Referred master registered but hasn't activated subscription
    ACTIVATED = "activated"  # Referred master activated subscription, reward given
    EXPIRED = "expired"  # Referral expired (30 days without activation)


class Referral(Base):
    """Referral tracking model."""
    
    __tablename__ = "referrals"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Referral relationship
    referrer_id: Mapped[int] = mapped_column(
        BigInteger, 
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Master who referred"
    )
    referred_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Master who was referred"
    )
    
    # Status and reward
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ReferralStatus.PENDING.value,
        index=True,
        comment="pending/activated/expired"
    )
    reward_given: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether reward was given"
    )
    reward_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        server_default="7",
        comment="Days added to subscription"
    )
    
    # Agent commission fields (NEW for agent network)
    commission_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default="10",
        comment="Commission percentage for agent (default 10%)"
    )
    commission_stars: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Commission amount in Telegram Stars"
    )
    payout_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
        comment="pending/sent/failed"
    )
    payout_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Telegram payment transaction ID"
    )
    payout_sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When commission was paid to agent"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="When referral activated subscription"
    )
    
    # Relationships
    referrer: Mapped["Master"] = relationship(
        "Master",
        foreign_keys=[referrer_id],
        back_populates="referrals_given"
    )
    referred: Mapped["Master"] = relationship(
        "Master",
        foreign_keys=[referred_id],
        back_populates="referral_received"
    )
    
    def __repr__(self) -> str:
        return f"<Referral(id={self.id}, referrer={self.referrer_id}, referred={self.referred_id}, status='{self.status}')>"
