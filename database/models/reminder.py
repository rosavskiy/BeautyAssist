"""Reminder model - represents scheduled notification."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.appointment import Appointment


class ReminderType(str, Enum):
    """Тип напоминания."""
    T_MINUS_24H = "t_minus_24h"  # За 24 часа до записи
    T_MINUS_2H = "t_minus_2h"  # За 2 часа до записи
    REACTIVATION = "reactivation"  # Реактивация старого клиента
    RESCHEDULED = "rescheduled"  # Запись перенесена
    CANCELLED_BY_MASTER = "cancelled_by_master"  # Запись отменена мастером


class ReminderChannel(str, Enum):
    """Reminder channel enum."""
    TELEGRAM = "telegram"
    SMS = "sms"
    EMAIL = "email"


class ReminderStatus(str, Enum):
    """Reminder status enum."""
    SCHEDULED = "scheduled"  # Запланировано
    SENT = "sent"  # Отправлено
    FAILED = "failed"  # Ошибка отправки
    CANCELLED = "cancelled"  # Отменено


class Reminder(Base):
    """Reminder model."""
    
    __tablename__ = "reminders"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Appointment relationship
    appointment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Reminder details
    reminder_type: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(
        String(20),
        default=ReminderChannel.TELEGRAM.value,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=ReminderStatus.SCHEDULED.value,
        nullable=False
    )
    
    # Scheduled time to send
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Actual sent time
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Additional data (JSON) for notification context
    extra_data: Mapped[dict | None] = mapped_column(
        type_=sa.JSON,
        nullable=True,
        comment="Additional data like old_time, reason, etc."
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="reminders")
    
    def __repr__(self) -> str:
        return (
            f"<Reminder(id={self.id}, appointment_id={self.appointment_id}, "
            f"type='{self.reminder_type}', status='{self.status}')>"
        )
