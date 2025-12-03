"""Payment model - represents payment for appointment."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    from database.models.appointment import Appointment


class PaymentMethod(str, Enum):
    """Payment method enum."""
    CASH = "cash"  # Наличные
    CARD = "card"  # Карта
    TRANSFER = "transfer"  # Перевод
    ACQUIRING = "acquiring"  # Эквайринг (онлайн)


class PaymentStatus(str, Enum):
    """Payment status enum."""
    PENDING = "pending"  # Ожидает оплаты
    PAID = "paid"  # Оплачено
    PARTIAL = "partial"  # Частично оплачено
    REFUNDED = "refunded"  # Возврат


class Payment(Base):
    """Payment model."""
    
    __tablename__ = "payments"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Appointment relationship (one-to-one)
    appointment_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Payment details
    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount in currency")
    method: Mapped[str] = mapped_column(
        String(20),
        default=PaymentMethod.CASH.value,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING.value,
        nullable=False
    )
    
    # Payment date (when actually paid)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="payment")
    
    def __repr__(self) -> str:
        return (
            f"<Payment(id={self.id}, appointment_id={self.appointment_id}, "
            f"amount={self.amount}, status='{self.status}')>"
        )
