"""Admin broadcast model for mass notifications."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base

if TYPE_CHECKING:
    pass


class AdminBroadcast(Base):
    """Admin broadcast messages history."""
    
    __tablename__ = "admin_broadcasts"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Message content
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="Broadcast message content")
    
    # Status
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Successfully sent messages")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Failed messages")
    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Total target recipients")
    
    # Metadata
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Admin telegram_id who created broadcast")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.timezone('UTC', func.now()),
        nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(nullable=True, comment="When broadcast started sending")
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True, comment="When broadcast finished")
    
    # Optional targeting
    target_filter: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True, 
        comment="Filter applied (e.g., 'all', 'premium', 'active')"
    )
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<AdminBroadcast(id={self.id}, "
            f"sent={self.sent_count}/{self.total_recipients}, "
            f"completed={self.is_completed})>"
        )
