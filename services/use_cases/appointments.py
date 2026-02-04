"""
Appointment use cases for business logic.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from pytz import timezone as pytz_timezone

from services.use_cases.base import BaseUseCase
from database.repositories import (
    AppointmentRepository,
    MasterRepository,
    ClientRepository,
    ServiceRepository,
    ReminderRepository,
)
from database.models import Appointment, AppointmentStatus, Service
from core.exceptions import (
    AppointmentNotFoundError,
    AppointmentConflictError,
    AppointmentStatusError,
    ServiceNotFoundError,
    ClientNotFoundError,
    NotRegisteredError,
)
from core.dto.appointments import CreateAppointmentDTO, CompleteAppointmentDTO


@dataclass
class AppointmentView:
    """View model for appointment display."""
    id: int
    client_name: str
    service_name: str
    start_time: datetime
    local_time_str: str
    price: int
    status: str


@dataclass
class DaySchedule:
    """View model for daily schedule."""
    date: datetime
    date_str: str
    appointments: List[AppointmentView]
    day_total: int


class GetAppointmentsUseCase(BaseUseCase[List[DaySchedule]]):
    """
    Get appointments for a master within a date range.
    
    Returns appointments grouped by day with calculated totals.
    """
    
    async def execute(
        self,
        telegram_id: int,
        days: int = 7,
        start_date: Optional[datetime] = None,
    ) -> List[DaySchedule]:
        """
        Get appointments grouped by day.
        
        Args:
            telegram_id: Master's Telegram ID
            days: Number of days to fetch
            start_date: Optional start date (defaults to now)
            
        Returns:
            List of DaySchedule with appointments grouped by day
            
        Raises:
            NotRegisteredError: If master not found
        """
        mrepo = MasterRepository(self.session)
        arepo = AppointmentRepository(self.session)
        srepo = ServiceRepository(self.session)
        crepo = ClientRepository(self.session)
        
        master = await mrepo.get_by_telegram_id(telegram_id)
        if not master:
            raise NotRegisteredError()
        
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        now_utc = start_date or datetime.now(timezone.utc)
        
        start_utc = now_utc
        end_utc = now_utc + timedelta(days=days)
        
        # Get appointments
        apps = await arepo.get_by_master(
            master.id,
            start_date=start_utc.replace(tzinfo=None),
            end_date=end_utc.replace(tzinfo=None)
        )
        
        # Filter by active statuses
        active_statuses = (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)
        apps = [a for a in apps if a.status in active_statuses]
        
        if not apps:
            return []
        
        # Prefetch services
        service_ids = set(a.service_id for a in apps)
        services = await srepo.get_by_ids(list(service_ids))
        svc_map = {s.id: s for s in services}
        
        # Group by local day
        by_day: Dict[datetime.date, List[Appointment]] = {}
        for a in apps:
            d_local = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz).date()
            by_day.setdefault(d_local, []).append(a)
        
        # Build result
        result = []
        for date in sorted(by_day.keys()):
            day_apps = sorted(by_day[date], key=lambda x: x.start_time)
            day_total = 0
            appointment_views = []
            
            for a in day_apps:
                svc = svc_map.get(a.service_id)
                client = await crepo.get_by_id(a.client_id)
                local_time = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                
                price = svc.price if svc and svc.price else 0
                day_total += price
                
                appointment_views.append(AppointmentView(
                    id=a.id,
                    client_name=client.name if client else "Клиент",
                    service_name=svc.name if svc else "Услуга",
                    start_time=a.start_time,
                    local_time_str=local_time.strftime('%H:%M'),
                    price=price,
                    status=a.status,
                ))
            
            result.append(DaySchedule(
                date=date,
                date_str=date.strftime('%d.%m.%Y'),
                appointments=appointment_views,
                day_total=day_total,
            ))
        
        return result


class CreateAppointmentUseCase(BaseUseCase[Appointment]):
    """
    Create a new appointment with all necessary validations.
    """
    
    async def execute(self, data: CreateAppointmentDTO) -> Appointment:
        """
        Create appointment with conflict checking and reminder setup.
        
        Args:
            data: Validated appointment creation data
            
        Returns:
            Created Appointment
            
        Raises:
            ServiceNotFoundError: If service not found
            ClientNotFoundError: If client not found  
            AppointmentConflictError: If time slot is taken
        """
        arepo = AppointmentRepository(self.session)
        srepo = ServiceRepository(self.session)
        crepo = ClientRepository(self.session)
        
        # Validate service exists
        service = await srepo.get_by_id(data.service_id)
        if not service:
            raise ServiceNotFoundError()
        
        # Validate client exists
        client = await crepo.get_by_id(data.client_id)
        if not client:
            raise ClientNotFoundError()
        
        # Calculate end time
        end_time = data.start_time + timedelta(minutes=service.duration_minutes)
        
        # Check for conflicts
        has_conflict = await arepo.check_time_conflict(
            data.master_id,
            data.start_time,
            end_time
        )
        if has_conflict:
            raise AppointmentConflictError(
                start_time=data.start_time.strftime('%H:%M'),
                end_time=end_time.strftime('%H:%M')
            )
        
        # Create appointment
        appointment = Appointment(
            master_id=data.master_id,
            client_id=data.client_id,
            service_id=data.service_id,
            start_time=data.start_time,
            end_time=end_time,
            status=AppointmentStatus.SCHEDULED.value,
            notes=data.notes,
        )
        
        self.session.add(appointment)
        await self.session.flush()
        
        # TODO: Create reminders via ReminderRepository
        
        return appointment


class CompleteAppointmentUseCase(BaseUseCase[Appointment]):
    """
    Complete an appointment (mark as completed or no-show).
    """
    
    async def execute(
        self,
        telegram_id: int,
        data: CompleteAppointmentDTO
    ) -> Appointment:
        """
        Complete appointment and update client stats.
        
        Args:
            telegram_id: Master's Telegram ID
            data: Completion data
            
        Returns:
            Updated Appointment
            
        Raises:
            NotRegisteredError: If master not found
            AppointmentNotFoundError: If appointment not found or not owned
        """
        mrepo = MasterRepository(self.session)
        arepo = AppointmentRepository(self.session)
        crepo = ClientRepository(self.session)
        srepo = ServiceRepository(self.session)
        
        master = await mrepo.get_by_telegram_id(telegram_id)
        if not master:
            raise NotRegisteredError()
        
        appointment = await arepo.get_by_id(data.appointment_id)
        if not appointment or appointment.master_id != master.id:
            raise AppointmentNotFoundError(data.appointment_id)
        
        # Update appointment status
        if data.client_showed:
            appointment.status = AppointmentStatus.COMPLETED.value
            appointment.is_completed = True
            
            # Get service price if not provided
            if data.payment_amount is None:
                service = await srepo.get_by_id(appointment.service_id)
                appointment.payment_amount = service.price if service else 0
            else:
                appointment.payment_amount = data.payment_amount
            
            # Update client stats
            client = await crepo.get_by_id(appointment.client_id)
            if client:
                client.total_visits += 1
                client.total_spent += appointment.payment_amount
                client.last_visit = appointment.start_time
                await crepo.update(client)
        else:
            appointment.status = AppointmentStatus.NO_SHOW.value
            appointment.is_completed = True
        
        if data.notes:
            appointment.notes = data.notes
        
        await arepo.update(appointment)
        return appointment


class CancelAppointmentUseCase(BaseUseCase[Appointment]):
    """
    Cancel an appointment.
    """
    
    async def execute(
        self,
        appointment_id: int,
        cancelled_by: str,  # 'master' or 'client'
        reason: Optional[str] = None
    ) -> Appointment:
        """
        Cancel appointment and notify relevant parties.
        
        Args:
            appointment_id: Appointment ID to cancel
            cancelled_by: Who cancelled ('master' or 'client')
            reason: Optional cancellation reason
            
        Returns:
            Updated Appointment
            
        Raises:
            AppointmentNotFoundError: If appointment not found
            AppointmentStatusError: If appointment cannot be cancelled
        """
        arepo = AppointmentRepository(self.session)
        rrepo = ReminderRepository(self.session)
        
        appointment = await arepo.get_by_id(appointment_id)
        if not appointment:
            raise AppointmentNotFoundError(appointment_id)
        
        # Check if can be cancelled
        if appointment.status in (AppointmentStatus.COMPLETED.value, AppointmentStatus.NO_SHOW.value):
            raise AppointmentStatusError(appointment.status, AppointmentStatus.CANCELLED.value)
        
        # Update status
        appointment.status = AppointmentStatus.CANCELLED.value
        if reason:
            appointment.notes = f"Отменено ({cancelled_by}): {reason}"
        
        await arepo.update(appointment)
        
        # Cancel pending reminders
        await rrepo.cancel_appointment_reminders(appointment_id)
        
        return appointment
