"""Service model - represents beauty service offered by master."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.master import Master
    from database.models.appointment import Appointment


class Service(Base):
    """Service model."""
    
    __tablename__ = "services"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Master relationship
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Service info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Category: brows, nails, lashes, hair, etc."
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Duration and price
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, comment="Price in master's currency")
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    master: Mapped["Master"] = relationship("Master", back_populates="services")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="service"
    )
    
    def __repr__(self) -> str:
        return f"<Service(id={self.id}, name='{self.name}', duration={self.duration_minutes}min, price={self.price})>"
