"""Reminder repository for database operations."""
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Reminder, ReminderStatus, ReminderType, ReminderChannel, Appointment


class ReminderRepository:
    """Repository for Reminder model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, reminder_id: int) -> Optional[Reminder]:
        """Get reminder by ID."""
        query = select(Reminder).where(Reminder.id == reminder_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_due_reminders(
        self,
        before_time: datetime,
        limit: int = 100
    ) -> List[Reminder]:
        """Get reminders that are scheduled to be sent before given time."""
        query = select(Reminder).where(
            and_(
                Reminder.status == ReminderStatus.SCHEDULED.value,
                Reminder.scheduled_time <= before_time
            )
        ).options(
            selectinload(Reminder.appointment).selectinload(Appointment.client),
            selectinload(Reminder.appointment).selectinload(Appointment.master),
            selectinload(Reminder.appointment).selectinload(Appointment.service)
        ).limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_by_appointment(
        self,
        appointment_id: int,
        status: Optional[ReminderStatus] = None
    ) -> List[Reminder]:
        """Get all reminders for an appointment."""
        query = select(Reminder).where(Reminder.appointment_id == appointment_id)
        
        if status:
            query = query.where(Reminder.status == status.value)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(
        self,
        appointment_id: int,
        reminder_type: ReminderType,
        scheduled_time: datetime,
        channel: ReminderChannel = ReminderChannel.TELEGRAM,
        extra_data: dict | None = None
    ) -> Reminder:
        """Create new reminder."""
        reminder = Reminder(
            appointment_id=appointment_id,
            reminder_type=reminder_type.value,
            channel=channel.value,
            scheduled_time=scheduled_time,
            status=ReminderStatus.SCHEDULED.value,
            extra_data=extra_data
        )
        
        self.session.add(reminder)
        await self.session.flush()
        return reminder
    
    async def update_status(
        self,
        reminder_id: int,
        status: ReminderStatus,
        sent_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> Optional[Reminder]:
        """Update reminder status."""
        reminder = await self.get_by_id(reminder_id)
        if reminder:
            reminder.status = status.value
            if sent_at:
                reminder.sent_at = sent_at
            if error_message:
                reminder.error_message = error_message[:500]  # Truncate to fit column
            await self.session.flush()
        return reminder
    
    async def cancel_appointment_reminders(self, appointment_id: int) -> int:
        """Cancel all pending reminders for an appointment. Returns count of cancelled reminders."""
        reminders = await self.get_by_appointment(appointment_id, status=ReminderStatus.SCHEDULED)
        count = 0
        for reminder in reminders:
            reminder.status = ReminderStatus.CANCELLED.value
            count += 1
        if count > 0:
            await self.session.flush()
        return count
