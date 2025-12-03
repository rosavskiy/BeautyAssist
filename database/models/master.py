"""Master model - represents beauty service master."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.service import Service
    from database.models.client import Client
    from database.models.appointment import Appointment


class Master(Base):
    """Master (beauty specialist) model."""
    
    __tablename__ = "masters"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Telegram info
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Personal info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Settings
    city: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="City for local timezone")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    
    # Working schedule (JSON format: {"monday": [["09:00", "18:00"]], "tuesday": ...})
    work_schedule: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Subscription
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    premium_until: Mapped[datetime | None] = mapped_column(nullable=True)
    
    # Referral
    referral_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    referred_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    # Onboarding
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    services: Mapped[list["Service"]] = relationship(
        "Service",
        back_populates="master",
        cascade="all, delete-orphan"
    )
    clients: Mapped[list["Client"]] = relationship(
        "Client",
        back_populates="master",
        cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="master",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Master(id={self.id}, name='{self.name}', telegram_id={self.telegram_id})>"
