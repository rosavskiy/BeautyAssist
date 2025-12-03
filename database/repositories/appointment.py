"""Appointment repository for database operations."""
from typing import Optional, List
from datetime import datetime, timedelta

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Appointment, AppointmentStatus


class AppointmentRepository:
    """Repository for Appointment model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(
        self,
        appointment_id: int,
        with_relations: bool = False
    ) -> Optional[Appointment]:
        """Get appointment by ID."""
        query = select(Appointment).where(Appointment.id == appointment_id)
        
        if with_relations:
            query = query.options(
                selectinload(Appointment.client),
                selectinload(Appointment.service),
                selectinload(Appointment.payment)
            )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_master(
        self,
        master_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        status: Optional[AppointmentStatus] = None,
    ) -> List[Appointment]:
        """Get appointments for master with optional filters."""
        query = select(Appointment).where(Appointment.master_id == master_id)
        
        if start_date:
            query = query.where(Appointment.start_time >= start_date)
        
        if end_date:
            query = query.where(Appointment.start_time <= end_date)
        
        if status:
            query = query.where(Appointment.status == status.value)
        
        query = query.order_by(Appointment.start_time)
        query = query.options(
            selectinload(Appointment.client),
            selectinload(Appointment.service)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def check_time_conflict(
        self,
        master_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_appointment_id: Optional[int] = None
    ) -> bool:
        """Check if time slot conflicts with existing appointments."""
        query = select(Appointment).where(
            and_(
                Appointment.master_id == master_id,
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.CONFIRMED.value
                ]),
                or_(
                    # New appointment starts during existing
                    and_(
                        Appointment.start_time <= start_time,
                        Appointment.end_time > start_time
                    ),
                    # New appointment ends during existing
                    and_(
                        Appointment.start_time < end_time,
                        Appointment.end_time >= end_time
                    ),
                    # New appointment contains existing
                    and_(
                        Appointment.start_time >= start_time,
                        Appointment.end_time <= end_time
                    )
                )
            )
        )
        
        if exclude_appointment_id:
            query = query.where(Appointment.id != exclude_appointment_id)
        
        result = await self.session.execute(query)
        return result.first() is not None
    
    async def create(
        self,
        master_id: int,
        client_id: int,
        service_id: int,
        start_time: datetime,
        end_time: datetime,
        comment: Optional[str] = None,
    ) -> Appointment:
        """Create new appointment."""
        appointment = Appointment(
            master_id=master_id,
            client_id=client_id,
            service_id=service_id,
            start_time=start_time,
            end_time=end_time,
            comment=comment,
            status=AppointmentStatus.SCHEDULED.value,
        )
        
        self.session.add(appointment)
        await self.session.flush()
        return appointment
    
    async def update_status(
        self,
        appointment_id: int,
        status: AppointmentStatus,
        cancellation_reason: Optional[str] = None
    ) -> Optional[Appointment]:
        """Update appointment status."""
        appointment = await self.get_by_id(appointment_id)
        if appointment:
            appointment.status = status.value
            if cancellation_reason:
                appointment.cancellation_reason = cancellation_reason
            await self.session.flush()
        return appointment

    async def update(self, appointment: Appointment) -> Appointment:
        """Generic updater for an appointment entity."""
        self.session.add(appointment)
        await self.session.flush()
        return appointment
    
    async def reschedule(
        self,
        appointment_id: int,
        new_start_time: datetime,
        new_end_time: datetime
    ) -> Optional[Appointment]:
        """Reschedule appointment."""
        appointment = await self.get_by_id(appointment_id)
        if appointment:
            appointment.start_time = new_start_time
            appointment.end_time = new_end_time
            appointment.status = AppointmentStatus.RESCHEDULED.value
            await self.session.flush()
        return appointment
    
    async def get_upcoming_for_reminders(
        self,
        hours_ahead: int = 24
    ) -> List[Appointment]:
        """Get appointments that need reminders."""
        now = datetime.utcnow()
        target_time = now + timedelta(hours=hours_ahead)
        
        # Get appointments around target time (±30 min window)
        query = select(Appointment).where(
            and_(
                Appointment.status.in_([
                    AppointmentStatus.SCHEDULED.value,
                    AppointmentStatus.CONFIRMED.value
                ]),
                Appointment.start_time >= target_time - timedelta(minutes=30),
                Appointment.start_time <= target_time + timedelta(minutes=30)
            )
        ).options(
            selectinload(Appointment.client),
            selectinload(Appointment.service),
            selectinload(Appointment.master)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
