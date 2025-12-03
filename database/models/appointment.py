"""Appointment model - represents client booking."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.master import Master
    from database.models.client import Client
    from database.models.service import Service
    from database.models.payment import Payment
    from database.models.reminder import Reminder


class AppointmentStatus(str, Enum):
    """Appointment status enum."""
    SCHEDULED = "scheduled"  # Запланирована
    CONFIRMED = "confirmed"  # Подтверждена клиентом
    RESCHEDULED = "rescheduled"  # Перенесена
    CANCELLED = "cancelled"  # Отменена
    COMPLETED = "completed"  # Завершена
    NO_SHOW = "no_show"  # Неявка


class Appointment(Base):
    """Appointment model."""
    
    __tablename__ = "appointments"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Relationships
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    client_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    service_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    
    # Appointment details
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=AppointmentStatus.SCHEDULED.value,
        nullable=False,
        index=True
    )
    
    # Additional info
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Completion tracking
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_amount: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Actual payment received")
    
    # If rescheduled, link to previous appointment
    rescheduled_from_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    master: Mapped["Master"] = relationship("Master", back_populates="appointments")
    client: Mapped["Client"] = relationship("Client", back_populates="appointments")
    service: Mapped["Service"] = relationship("Service", back_populates="appointments")
    payment: Mapped["Payment | None"] = relationship(
        "Payment",
        back_populates="appointment",
        uselist=False
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        "Reminder",
        back_populates="appointment",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Appointment(id={self.id}, master_id={self.master_id}, "
            f"client_id={self.client_id}, start_time={self.start_time}, status='{self.status}')>"
        )
