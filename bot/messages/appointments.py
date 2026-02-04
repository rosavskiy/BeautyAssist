"""Appointment-related messages."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class AppointmentMessages:
    """Messages for appointment management."""
    
    # List views
    NO_APPOINTMENTS_NEXT_DAYS = "В ближайшие дни записей нет"
    NO_APPOINTMENTS_WEEK = "В ближайшую неделю записей нет"
    
    # Status changes
    APPOINTMENT_COMPLETED = "✅ <b>Запись завершена</b>"
    APPOINTMENT_CANCELLED = "❌ <b>Запись отменена</b>"
    APPOINTMENT_CONFIRMED = "✅ <b>Запись подтверждена!</b>"
    
    # Errors
    INVALID_APPOINTMENT_ID = "Ошибка: неверный ID записи"
    APPOINTMENT_NOT_FOUND = "Запись не найдена"
    
    @staticmethod
    def format_rub(amount: int) -> str:
        """Format amount as rubles."""
        return f"{amount:,}".replace(",", " ") + " ₽"
    
    @staticmethod
    def appointments_for_date(date_str: str) -> str:
        return f"Записи на {date_str}:"
    
    @staticmethod
    def day_forecast(amount: int) -> str:
        return f"Прогноз за день: {AppointmentMessages.format_rub(amount)}"
    
    @staticmethod
    def week_forecast(amount: int) -> str:
        return f"Прогноз за неделю: {AppointmentMessages.format_rub(amount)}"
    
    @staticmethod
    def day_total(amount: int) -> str:
        return f"Итого за день: {AppointmentMessages.format_rub(amount)}"
    
    @staticmethod
    def appointment_line(time: str, service: str, client: str, price: int) -> str:
        """Format single appointment line."""
        return f"- {time} {service} — {client} ({AppointmentMessages.format_rub(price)})"
    
    @staticmethod
    def complete_appointment_question(
        client_name: str,
        service_name: str,
        datetime_str: str
    ) -> str:
        """Message for completing appointment."""
        return (
            f"📋 <b>Завершить запись?</b>\n\n"
            f"Клиент: {client_name}\n"
            f"Услуга: {service_name}\n"
            f"Время: {datetime_str}\n\n"
            f"Клиент пришёл?"
        )
    
    @staticmethod
    def appointment_completed_details(client_name: str, amount: int) -> str:
        """Details after completing appointment."""
        return (
            f"✅ <b>Запись завершена</b>\n\n"
            f"Клиент: {client_name}\n"
            f"Оплата: {amount} ₽"
        )
    
    @staticmethod
    def client_no_show(client_name: str) -> str:
        """Message when client didn't show up."""
        return f"❌ <b>Отмечено: клиент не пришёл</b>\n\nКлиент: {client_name}"
    
    @staticmethod
    def client_confirmation_thanks(datetime_str: str) -> str:
        """Thank client for confirming."""
        return (
            f"✅ <b>Запись подтверждена!</b>\n\n"
            f"Спасибо! Ждём вас {datetime_str}"
        )
    
    @staticmethod
    def master_notification_confirmed(
        client_name: str,
        client_phone: str,
        service_name: str,
        datetime_str: str
    ) -> str:
        """Notify master that client confirmed."""
        return (
            f"✅ <b>Клиент подтвердил запись!</b>\n\n"
            f"👤 {client_name}\n"
            f"📱 {client_phone}\n"
            f"📋 {service_name}\n"
            f"📅 {datetime_str}"
        )
    
    @staticmethod
    def cancel_confirmation(datetime_str: str) -> str:
        """Ask client to confirm cancellation."""
        return (
            f"⚠️ <b>Отмена записи</b>\n\n"
            f"Вы уверены, что хотите отменить запись на {datetime_str}?\n\n"
            f"Пожалуйста, предупредите мастера заранее, чтобы он мог освободить время для других клиентов."
        )
    
    @staticmethod
    def cancelled_by_client(datetime_str: str) -> str:
        """Confirm cancellation to client."""
        return (
            f"❌ <b>Запись отменена</b>\n\n"
            f"Запись на {datetime_str} отменена.\n"
            f"Будем рады видеть вас в другое время!"
        )
    
    @staticmethod
    def master_notification_cancelled(
        client_name: str,
        client_phone: str,
        service_name: str,
        datetime_str: str
    ) -> str:
        """Notify master that client cancelled."""
        return (
            f"❌ <b>Клиент отменил запись</b>\n\n"
            f"👤 {client_name}\n"
            f"📱 {client_phone}\n"
            f"📋 {service_name}\n"
            f"📅 {datetime_str}\n\n"
            f"Время освободилось для других клиентов."
        )
    
    # Weekday translations
    WEEKDAYS = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье',
    }
    
    @staticmethod
    def translate_weekday(date_str: str) -> str:
        """Translate English weekday name in string to Russian."""
        result = date_str
        for eng, rus in AppointmentMessages.WEEKDAYS.items():
            result = result.replace(eng, rus)
        return result
