"""Scheduling logic: compute available slots and reminders (skeleton)."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Tuple

from database.models import Master, Service, Appointment, AppointmentStatus
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
