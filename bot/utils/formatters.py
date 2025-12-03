"""Message formatting utilities."""
from typing import Optional
from datetime import datetime

from database.models import Master, Client, Service, Appointment, Payment
from bot.utils.time_utils import format_datetime, format_date, format_time


def format_master_info(master: Master) -> str:
    """Format master information."""
    lines = [
        f"👤 <b>{master.name}</b>",
        f"📱 Telegram: @{master.telegram_username or 'не указан'}",
    ]
    
    if master.phone:
        lines.append(f"☎️ Телефон: {master.phone}")
    
    lines.extend([
        f"🌍 Часовой пояс: {master.timezone}",
        f"💳 Тариф: {'Premium' if master.is_premium else 'Free'}",
        f"🔗 Реферальный код: <code>{master.referral_code}</code>"
    ])
    
    return "\n".join(lines)


def format_service_info(service: Service, with_master: bool = False) -> str:
    """Format service information."""
    lines = [
        f"<b>{service.name}</b>",
        f"⏱ Длительность: {service.duration_minutes} мин",
        f"💰 Цена: {service.price} ₽",
    ]
    
    if service.category:
        lines.insert(1, f"📂 Категория: {service.category}")
    
    if service.description:
        lines.append(f"📝 {service.description}")
    
    return "\n".join(lines)


def format_service_list(services: list[Service]) -> str:
    """Format list of services."""
    if not services:
        return "Услуги не добавлены"
    
    lines = ["<b>Ваши услуги:</b>\n"]
    for i, service in enumerate(services, 1):
        status = "✅" if service.is_active else "❌"
        lines.append(
            f"{status} {i}. <b>{service.name}</b> — {service.duration_minutes} мин, {service.price} ₽"
        )
    
    return "\n".join(lines)


def format_client_info(client: Client) -> str:
    """Format client information."""
    lines = [
        f"<b>{client.name}</b>",
        f"📱 {client.phone}",
    ]
    
    if client.telegram_username:
        lines.append(f"💬 @{client.telegram_username}")
    
    if client.source:
        lines.append(f"📍 Источник: {client.source}")
    
    lines.extend([
        f"\n📊 Статистика:",
        f"Визитов: {client.total_visits}",
        f"Потрачено: {client.total_spent} ₽",
    ])
    
    if client.last_visit:
        lines.append(f"Последний визит: {format_date(client.last_visit)}")
    
    if client.notes:
        lines.append(f"\n📝 Заметки: {client.notes}")
    
    return "\n".join(lines)


def format_appointment_info(appointment: Appointment, detailed: bool = True) -> str:
    """Format appointment information."""
    lines = [
        f"📅 <b>Запись #{appointment.id}</b>",
        f"👤 Клиент: {appointment.client.name}",
        f"💅 Услуга: {appointment.service.name}",
        f"🕐 Время: {format_datetime(appointment.start_time)}",
        f"⏱ Длительность: {appointment.service.duration_minutes} мин",
        f"💰 Стоимость: {appointment.service.price} ₽",
    ]
    
    # Status emoji
    status_emoji = {
        "scheduled": "🕒",
        "confirmed": "✅",
        "rescheduled": "🔄",
        "cancelled": "❌",
        "completed": "✔️",
        "no_show": "👻"
    }
    
    status_names = {
        "scheduled": "Запланирована",
        "confirmed": "Подтверждена",
        "rescheduled": "Перенесена",
        "cancelled": "Отменена",
        "completed": "Завершена",
        "no_show": "Неявка"
    }
    
    emoji = status_emoji.get(appointment.status, "")
    status_name = status_names.get(appointment.status, appointment.status)
    lines.append(f"{emoji} Статус: {status_name}")
    
    if detailed:
        if appointment.comment:
            lines.append(f"\n💬 Комментарий: {appointment.comment}")
        
        if appointment.payment:
            payment_status = "✅ Оплачено" if appointment.payment.status == "paid" else "⏳ Ожидает оплаты"
            lines.append(f"💳 {payment_status}")
    
    return "\n".join(lines)


def format_appointment_short(appointment: Appointment) -> str:
    """Format short appointment information for lists."""
    return (
        f"{format_time(appointment.start_time)} — "
        f"<b>{appointment.client.name}</b> ({appointment.service.name})"
    )


def format_daily_schedule(appointments: list[Appointment], date: datetime) -> str:
    """Format daily schedule."""
    if not appointments:
        return f"📅 {format_date(date)}\n\nЗаписей нет"
    
    lines = [
        f"📅 <b>{format_date(date)}</b>\n",
        f"Всего записей: {len(appointments)}\n"
    ]
    
    for app in sorted(appointments, key=lambda x: x.start_time):
        lines.append(format_appointment_short(app))
    
    return "\n".join(lines)


def format_report(
    period_start: datetime,
    period_end: datetime,
    total_appointments: int,
    completed: int,
    no_shows: int,
    cancelled: int,
    total_revenue: int,
    total_expenses: int = 0
) -> str:
    """Format financial report."""
    net_profit = total_revenue - total_expenses
    
    lines = [
        f"📊 <b>Отчёт за период</b>",
        f"📅 {format_date(period_start)} — {format_date(period_end)}\n",
        f"<b>Записи:</b>",
        f"Всего: {total_appointments}",
        f"Завершено: {completed}",
        f"Неявки: {no_shows}",
        f"Отменено: {cancelled}\n",
        f"<b>Финансы:</b>",
        f"💰 Выручка: {total_revenue} ₽",
    ]
    
    if total_expenses > 0:
        lines.extend([
            f"💸 Расходы: {total_expenses} ₽",
            f"💵 Чистая прибыль: {net_profit} ₽"
        ])
    
    return "\n".join(lines)
