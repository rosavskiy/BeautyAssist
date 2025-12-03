"""Expense model - represents master's expenses."""
from datetime import datetime

from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class Expense(Base):
    """Expense model."""
    
    __tablename__ = "expenses"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Master relationship
    master_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("masters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Expense details
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Category: materials, rent, advertising, etc."
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount in currency")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Date when expense occurred
    expense_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return (
            f"<Expense(id={self.id}, master_id={self.master_id}, "
            f"category='{self.category}', amount={self.amount})>"
        )
