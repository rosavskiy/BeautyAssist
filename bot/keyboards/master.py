"""Master keyboards for inline buttons."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu keyboard for master."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📋 Записи", callback_data="master:appointments"),
        InlineKeyboardButton(text="💅 Услуги", callback_data="master:services")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Клиенты", callback_data="master:clients"),
        InlineKeyboardButton(text="📊 Отчёты", callback_data="master:reports")
    )
    builder.row(
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="master:settings"),
        InlineKeyboardButton(text="ℹ️ Помощь", callback_data="master:help")
    )
    
    return builder.as_markup()


def get_services_keyboard(services: list, include_add: bool = True) -> InlineKeyboardMarkup:
    """Get keyboard with services list."""
    builder = InlineKeyboardBuilder()
    
    for service in services:
        status = "✅" if service.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {service.name} — {service.price} ₽",
                callback_data=f"service:view:{service.id}"
            )
        )
    
    if include_add:
        builder.row(
            InlineKeyboardButton(text="➕ Добавить услугу", callback_data="service:add")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="master:menu")
    )
    
    return builder.as_markup()


def get_service_actions_keyboard(service_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Get keyboard with service actions."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"service:edit:{service_id}")
    )
    
    if is_active:
        builder.row(
            InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"service:deactivate:{service_id}")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="✅ Активировать", callback_data=f"service:activate:{service_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 К списку услуг", callback_data="master:services")
    )
    
    return builder.as_markup()


def get_appointments_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for appointments management."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="appointments:today"),
        InlineKeyboardButton(text="🗓 Неделя", callback_data="appointments:week")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Новая запись", callback_data="appointment:create")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="master:menu")
    )
    
    return builder.as_markup()


def get_appointment_actions_keyboard(appointment_id: int, status: str) -> InlineKeyboardMarkup:
    """Get keyboard with appointment actions."""
    builder = InlineKeyboardBuilder()
    
    if status in ["scheduled", "confirmed"]:
        builder.row(
            InlineKeyboardButton(text="✅ Завершить", callback_data=f"appointment:complete:{appointment_id}")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Перенести", callback_data=f"appointment:reschedule:{appointment_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"appointment:cancel:{appointment_id}")
        )
        builder.row(
            InlineKeyboardButton(text="👻 Неявка", callback_data=f"appointment:no_show:{appointment_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 К записям", callback_data="master:appointments")
    )
    
    return builder.as_markup()


def get_back_keyboard(callback_data: str = "master:menu") -> InlineKeyboardMarkup:
    """Get simple back button keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=callback_data)
    )
    return builder.as_markup()


def get_confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{action}:confirm:{item_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"{action}:cancel:{item_id}")
    )
    
    return builder.as_markup()


def get_weekdays_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting working days."""
    builder = InlineKeyboardBuilder()
    
    weekdays = [
        ("Пн", "monday"),
        ("Вт", "tuesday"),
        ("Ср", "wednesday"),
        ("Чт", "thursday"),
        ("Пт", "friday"),
        ("Сб", "saturday"),
        ("Вс", "sunday"),
    ]
    
    row = []
    for name, key in weekdays:
        row.append(InlineKeyboardButton(text=name, callback_data=f"weekday:{key}"))
        if len(row) == 3:
            builder.row(*row)
            row = []
    
    if row:
        builder.row(*row)
    
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data="weekday:done")
    )
    
    return builder.as_markup()
