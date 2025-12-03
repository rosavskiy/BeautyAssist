"""Time utilities for slot generation and scheduling."""
from datetime import datetime, timedelta, time
from typing import List, Tuple, Optional
import pytz


def parse_time(time_str: str) -> time:
    """Parse time string in format HH:MM."""
    try:
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM")


def generate_time_slots(
    start_time: time,
    end_time: time,
    duration_minutes: int,
    date: datetime
) -> List[Tuple[datetime, datetime]]:
    """Generate time slots for a given day."""
    slots = []
    
    # Combine date with start time
    current = datetime.combine(date.date(), start_time)
    end = datetime.combine(date.date(), end_time)
    
    # Generate slots
    while current + timedelta(minutes=duration_minutes) <= end:
        slot_end = current + timedelta(minutes=duration_minutes)
        slots.append((current, slot_end))
        current = slot_end
    
    return slots


def generate_half_hour_slots(
    start_time: time,
    end_time: time,
    date: datetime
) -> List[datetime]:
    """Generate 30-minute step start times within working interval."""
    slots = []
    current = datetime.combine(date.date(), start_time)
    end = datetime.combine(date.date(), end_time)
    step = timedelta(minutes=30)
    while current < end:
        slots.append(current)
        current += step
    return slots


def get_available_dates(days_ahead: int = 14) -> List[datetime]:
    """Get list of dates for next N days."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return [today + timedelta(days=i) for i in range(days_ahead)]


def format_datetime(dt: datetime, timezone_str: str = "Europe/Moscow") -> str:
    """Format datetime to readable string with timezone."""
    tz = pytz.timezone(timezone_str)
    local_dt = dt.astimezone(tz) if dt.tzinfo else tz.localize(dt)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def format_date(dt: datetime) -> str:
    """Format date to readable string."""
    return dt.strftime("%d.%m.%Y")


def format_time(dt: datetime) -> str:
    """Format time to readable string."""
    return dt.strftime("%H:%M")


def get_weekday_name_ru(date: datetime) -> str:
    """Get Russian weekday name."""
    weekdays = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье"
    }
    return weekdays[date.weekday()]


def get_weekday_short_ru(date: datetime) -> str:
    """Get short Russian weekday name."""
    weekdays = {
        0: "Пн",
        1: "Вт",
        2: "Ср",
        3: "Чт",
        4: "Пт",
        5: "Сб",
        6: "Вс"
    }
    return weekdays[date.weekday()]


def parse_work_schedule(schedule_dict: dict, date: datetime) -> Optional[List[Tuple[time, time]]]:
    """Parse work schedule for specific date."""
    weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    weekday = weekday_names[date.weekday()]
    
    if weekday not in schedule_dict:
        return None
    
    intervals = schedule_dict[weekday]
    if not intervals:
        return None
    
    result = []
    for interval in intervals:
        start = parse_time(interval[0])
        end = parse_time(interval[1])
        result.append((start, end))
    
    return result


def is_working_day(schedule_dict: dict, date: datetime) -> bool:
    """Check if date is a working day."""
    return parse_work_schedule(schedule_dict, date) is not None
