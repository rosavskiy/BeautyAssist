"""Notification sending and reminder scanning."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import List

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from pytz import timezone as pytz_timezone

from database.models import ReminderStatus, ReminderType
from database.repositories import ReminderRepository


async def send_due_reminders(bot: Bot, session: AsyncSession) -> int:
    """
    Scan and send all due reminders.
    
    Args:
        bot: Telegram bot instance
        session: Database session
    
    Returns:
        Number of reminders sent
    """
    now = datetime.now(timezone.utc)
    reminder_repo = ReminderRepository(session)
    
    # Get all reminders due to be sent
    reminders = await reminder_repo.get_due_reminders(before_time=now, limit=100)
    
    sent = 0
    for reminder in reminders:
        try:
            app = reminder.appointment
            if not app or not app.client or not app.master:
                # Invalid data: cancel reminder
                await reminder_repo.update_status(
                    reminder.id,
                    ReminderStatus.CANCELLED,
                    error_message="Missing appointment/client/master data"
                )
                continue
            
            # Skip if appointment is cancelled or completed
            if app.status in ["cancelled", "completed", "no_show"]:
                await reminder_repo.update_status(
                    reminder.id,
                    ReminderStatus.CANCELLED,
                    error_message=f"Appointment status: {app.status}"
                )
                continue
            
            # Get master's timezone for formatting
            tz_name = app.master.timezone or "Europe/Moscow"
            try:
                tz = pytz_timezone(tz_name)
                local_start = app.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                date_str = local_start.strftime('%d.%m.%Y')
                time_str = local_start.strftime('%H:%M')
            except Exception:
                date_str = app.start_time.strftime('%d.%m.%Y')
                time_str = app.start_time.strftime('%H:%M')
            
            service_name = app.service.name if app.service else "Услуга"
            master_name = app.master.name
            
            # Prepare message based on reminder type
            keyboard = None
            if reminder.reminder_type == ReminderType.T_MINUS_24H.value:
                text = (
                    f"⏰ <b>Напоминание о записи</b>\n\n"
                    f"Завтра в <b>{time_str}</b> у вас запись:\n"
                    f"📋 <i>{service_name}</i>\n"
                    f"👤 Мастер: {master_name}\n\n"
                    f"Пожалуйста, подтвердите, что придёте!"
                )
                # Add confirmation button
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="✅ Подтверждаю, приду",
                        callback_data=f"client_confirm:{app.id}"
                    )],
                    [InlineKeyboardButton(
                        text="❌ Не смогу прийти",
                        callback_data=f"client_cancel:{app.id}"
                    )]
                ])
            elif reminder.reminder_type == ReminderType.T_MINUS_2H.value:
                text = (
                    f"⏰ <b>Напоминание о записи</b>\n\n"
                    f"Через 2 часа (в <b>{time_str}</b>) у вас запись:\n"
                    f"📋 <i>{service_name}</i>\n"
                    f"👤 Мастер: {master_name}\n\n"
                    f"Если не можете прийти, пожалуйста, предупредите заранее."
                )
            elif reminder.reminder_type == ReminderType.RESCHEDULED.value:
                # Запись перенесена мастером
                old_time = reminder.extra_data.get('old_time') if reminder.extra_data else None
                text = (
                    f"🔄 <b>Мастер перенес вашу запись</b>\n\n"
                    f"📋 Услуга: <i>{service_name}</i>\n"
                )
                if old_time:
                    text += f"Было: {old_time}\n"
                text += (
                    f"Стало: <b>{date_str} в {time_str}</b> ({tz_name})\n\n"
                    f"👤 Мастер: {master_name}"
                )
            elif reminder.reminder_type == ReminderType.CANCELLED_BY_MASTER.value:
                # Запись отменена мастером
                reason = reminder.extra_data.get('reason') if reminder.extra_data else None
                text = (
                    f"❌ <b>Мастер отменил запись</b>\n\n"
                    f"📋 Услуга: <i>{service_name}</i>\n"
                    f"📅 Дата: {date_str} в {time_str} ({tz_name})\n"
                )
                if reason:
                    text += f"💬 Причина: {reason}\n"
                text += f"\nВы можете записаться на другое время через бота."
            elif reminder.reminder_type == ReminderType.REACTIVATION.value:
                text = (
                    f"👋 <b>Давно не виделись!</b>\n\n"
                    f"Прошло уже 3 недели с вашего последнего визита к мастеру {master_name}.\n"
                    f"Может быть, пора записаться снова? 😊\n\n"
                    f"Свяжитесь с мастером для записи."
                )
            else:
                text = f"Напоминание о записи {date_str} в {time_str}"
            
            # Try to send to client
            recipient_id = None
            if app.client.telegram_id:
                recipient_id = app.client.telegram_id
            elif app.master.telegram_id:
                # If client has no Telegram, notify master
                text = (
                    f"⚠️ <b>Не удалось отправить напоминание клиенту</b>\n\n"
                    f"Клиент: {app.client.name}\n"
                    f"Телефон: {app.client.phone}\n"
                    f"Запись: {date_str} в {time_str}\n"
                    f"Услуга: {service_name}\n\n"
                    f"Пожалуйста, напомните клиенту о записи вручную."
                )
                recipient_id = app.master.telegram_id
            
            if recipient_id:
                await bot.send_message(
                    recipient_id, 
                    text, 
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
                await reminder_repo.update_status(
                    reminder.id,
                    ReminderStatus.SENT,
                    sent_at=now
                )
                sent += 1
            else:
                await reminder_repo.update_status(
                    reminder.id,
                    ReminderStatus.FAILED,
                    error_message="No telegram_id for client or master"
                )
        
        except Exception as e:
            # Mark as failed
            error_msg = str(e)[:490]
            await reminder_repo.update_status(
                reminder.id,
                ReminderStatus.FAILED,
                error_message=error_msg
            )
    
    # Commit all status updates
    await session.commit()
    return sent

