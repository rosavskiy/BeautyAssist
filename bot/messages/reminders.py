"""Reminder-related messages."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReminderMessages:
    """Messages for appointment reminders."""
    
    @staticmethod
    def reminder_24h(
        time_str: str,
        service_name: str,
        master_name: str
    ) -> str:
        """24-hour reminder before appointment."""
        return (
            f"⏰ <b>Напоминание о записи</b>\n\n"
            f"Завтра в <b>{time_str}</b> у вас запись:\n"
            f"📋 <i>{service_name}</i>\n"
            f"👤 Мастер: {master_name}\n\n"
            f"Пожалуйста, подтвердите, что придёте!"
        )
    
    @staticmethod
    def reminder_2h(
        time_str: str,
        service_name: str,
        master_name: str
    ) -> str:
        """2-hour reminder before appointment."""
        return (
            f"⏰ <b>Напоминание о записи</b>\n\n"
            f"Через 2 часа (в <b>{time_str}</b>) у вас запись:\n"
            f"📋 <i>{service_name}</i>\n"
            f"👤 Мастер: {master_name}\n\n"
            f"Если не можете прийти, пожалуйста, предупредите заранее."
        )
    
    @staticmethod
    def appointment_rescheduled(
        service_name: str,
        new_date: str,
        new_time: str,
        timezone_name: str,
        master_name: str,
        old_time: Optional[str] = None
    ) -> str:
        """Appointment rescheduled by master."""
        text = (
            f"🔄 <b>Мастер перенес вашу запись</b>\n\n"
            f"📋 Услуга: <i>{service_name}</i>\n"
        )
        if old_time:
            text += f"Было: {old_time}\n"
        text += (
            f"Стало: <b>{new_date} в {new_time}</b> ({timezone_name})\n\n"
            f"👤 Мастер: {master_name}"
        )
        return text
    
    @staticmethod
    def appointment_cancelled_by_master(
        service_name: str,
        date_str: str,
        time_str: str,
        timezone_name: str,
        reason: Optional[str] = None
    ) -> str:
        """Appointment cancelled by master."""
        text = (
            f"❌ <b>Мастер отменил запись</b>\n\n"
            f"📋 Услуга: <i>{service_name}</i>\n"
            f"📅 Дата: {date_str} в {time_str} ({timezone_name})\n"
        )
        if reason:
            text += f"💬 Причина: {reason}\n"
        text += "\nВы можете записаться на другое время через бота."
        return text
    
    @staticmethod
    def reactivation_reminder(master_name: str) -> str:
        """Reminder to inactive client."""
        return (
            f"👋 <b>Давно не виделись!</b>\n\n"
            f"Прошло уже 3 недели с вашего последнего визита к мастеру {master_name}.\n"
            f"Может быть, пора записаться снова? 😊\n\n"
            f"Свяжитесь с мастером для записи."
        )
    
    @staticmethod
    def failed_to_send_to_client(
        client_name: str,
        client_phone: str,
        date_str: str,
        time_str: str,
        service_name: str
    ) -> str:
        """Notify master that reminder couldn't be sent to client."""
        return (
            f"⚠️ <b>Не удалось отправить напоминание клиенту</b>\n\n"
            f"Клиент: {client_name}\n"
            f"Телефон: {client_phone}\n"
            f"Запись: {date_str} в {time_str}\n"
            f"Услуга: {service_name}\n\n"
            f"Пожалуйста, напомните клиенту о записи вручную."
        )
