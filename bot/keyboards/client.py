"""Client keyboards for inline buttons."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime


def get_services_selection_keyboard(services: list, master_code: str) -> InlineKeyboardMarkup:
    """Get keyboard for client to select service."""
    builder = InlineKeyboardBuilder()
    
    for service in services:
        builder.row(
            InlineKeyboardButton(
                text=f"{service.name} — {service.duration_minutes} мин, {service.price} ₽",
                callback_data=f"book:service:{master_code}:{service.id}"
            )
        )
    
    return builder.as_markup()


def get_dates_keyboard(dates: list[datetime], master_code: str, service_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for client to select date."""
    builder = InlineKeyboardBuilder()
    
    from bot.utils.time_utils import format_date, get_weekday_short_ru
    
    for date in dates:
        date_str = format_date(date)
        weekday = get_weekday_short_ru(date)
        builder.row(
            InlineKeyboardButton(
                text=f"{weekday}, {date_str}",
                callback_data=f"book:date:{master_code}:{service_id}:{date.strftime('%Y-%m-%d')}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"book:back:{master_code}")
    )
    
    return builder.as_markup()


def get_time_slots_keyboard(
    slots: list[tuple[datetime, datetime]],
    master_code: str,
    service_id: int,
    date_str: str
) -> InlineKeyboardMarkup:
    """Get keyboard for client to select time slot."""
    builder = InlineKeyboardBuilder()
    
    from bot.utils.time_utils import format_time
    
    # Group slots by 3 per row
    row = []
    for start, end in slots:
        time_str = format_time(start)
        row.append(
            InlineKeyboardButton(
                text=time_str,
                callback_data=f"book:slot:{master_code}:{service_id}:{date_str}:{start.strftime('%H:%M')}"
            )
        )
        
        if len(row) == 3:
            builder.row(*row)
            row = []
    
    if row:
        builder.row(*row)
    
    builder.row(
        InlineKeyboardButton(
            text="🔙 К выбору даты",
            callback_data=f"book:date_back:{master_code}:{service_id}"
        )
    )
    
    return builder.as_markup()


def get_booking_confirm_keyboard(
    master_code: str,
    service_id: int,
    date_str: str,
    time_str: str
) -> InlineKeyboardMarkup:
    """Get keyboard for booking confirmation."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить запись",
            callback_data=f"book:confirm:{master_code}:{service_id}:{date_str}:{time_str}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Выбрать другое время",
            callback_data=f"book:date_back:{master_code}:{service_id}"
        )
    )
    
    return builder.as_markup()


def get_appointment_client_actions_keyboard(appointment_id: int) -> InlineKeyboardMarkup:
    """Get keyboard for client's appointment actions."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text="🔄 Перенести",
            callback_data=f"client:reschedule:{appointment_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить",
            callback_data=f"client:cancel:{appointment_id}"
        )
    )
    
    return builder.as_markup()
