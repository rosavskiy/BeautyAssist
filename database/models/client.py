"""Client model - represents master's client."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.master import Master
    from database.models.appointment import Appointment


class Client(Base):
    """Client model."""
    
    __tablename__ = "clients"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Master relationship
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Telegram info (if client uses bot)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Personal info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Additional info
    source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Source: instagram, referral, website, etc."
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Master's notes about client (allergies, preferences, etc.)"
    )
    
    # Statistics
    last_visit: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_visits: Mapped[int] = mapped_column(default=0, nullable=False)
    total_spent: Mapped[int] = mapped_column(default=0, nullable=False, comment="Total spent in currency")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    master: Mapped["Master"] = relationship("Master", back_populates="clients")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="client",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name='{self.name}', phone='{self.phone}')>"
