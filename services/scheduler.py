"""Scheduling logic: compute available slots and reminders."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Master, Service, Appointment, AppointmentStatus
from database.models.reminder import ReminderType, ReminderChannel
from database.repositories import ReminderRepository
from bot.utils.time_utils import parse_work_schedule, generate_time_slots


def compute_available_slots(master: Master, service: Service, date: datetime, existing: List[Appointment]) -> List[Tuple[datetime, datetime]]:
    intervals = parse_work_schedule(master.work_schedule or {}, date)
    if not intervals:
        return []
    busy = [(a.start_time, a.end_time) for a in existing if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)]
    slots: List[Tuple[datetime, datetime]] = []
    day_start = datetime(date.year, date.month, date.day)
    for st, et in intervals:
        for s, e in generate_time_slots(st, et, service.duration_minutes, day_start):
            if s <= datetime.utcnow():
                continue
            # overlap check
            if any((s < b_end and e > b_start) for b_start, b_end in busy):
                continue
            slots.append((s, e))
    return slots


def schedule_default_reminders(start_time: datetime) -> List[datetime]:
    """Compute default reminder moments: T-24h, T-2h, and reactivation (21 days after)."""
    t24 = start_time - timedelta(hours=24)
    t2 = start_time - timedelta(hours=2)
    reac = start_time + timedelta(days=21)
    return [t24, t2, reac]


async def create_appointment_reminders(
    session: AsyncSession,
    appointment: Appointment,
    cancel_existing: bool = True
) -> int:
    """
    Create reminders for an appointment.
    
    Args:
        session: Database session
        appointment: Appointment to create reminders for
        cancel_existing: If True, cancel existing reminders before creating new ones
    
    Returns:
        Number of reminders created
    """
    reminder_repo = ReminderRepository(session)
    
    # Cancel existing reminders if requested (e.g., when rescheduling)
    if cancel_existing:
        await reminder_repo.cancel_appointment_reminders(appointment.id)
    
    # Don't create reminders for cancelled/completed appointments
    if appointment.status in [AppointmentStatus.CANCELLED.value, AppointmentStatus.COMPLETED.value, AppointmentStatus.NO_SHOW.value]:
        return 0
    
    from datetime import timezone
    now = datetime.now(timezone.utc)
    created_count = 0
    
    # T-24h reminder
    t_24h = appointment.start_time - timedelta(hours=24)
    if t_24h > now:
        await reminder_repo.create(
            appointment_id=appointment.id,
            reminder_type=ReminderType.T_MINUS_24H,
            scheduled_time=t_24h,
            channel=ReminderChannel.TELEGRAM
        )
        created_count += 1
    
    # T-2h reminder
    t_2h = appointment.start_time - timedelta(hours=2)
    if t_2h > now:
        await reminder_repo.create(
            appointment_id=appointment.id,
            reminder_type=ReminderType.T_MINUS_2H,
            scheduled_time=t_2h,
            channel=ReminderChannel.TELEGRAM
        )
        created_count += 1
    
    # Reactivation reminder (21 days after appointment)
    reactivation_time = appointment.start_time + timedelta(days=21)
    if reactivation_time > now:
        await reminder_repo.create(
            appointment_id=appointment.id,
            reminder_type=ReminderType.REACTIVATION,
            scheduled_time=reactivation_time,
            channel=ReminderChannel.TELEGRAM
        )
        created_count += 1
    
    await session.flush()
    return created_count

