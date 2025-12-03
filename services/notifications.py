"""Notification sending and reminder scanning (skeleton)."""
from __future__ import annotations
from datetime import datetime
from typing import List

from aiogram import Bot
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Reminder, ReminderStatus, Appointment, ReminderType


async def send_due_reminders(bot: Bot, session: AsyncSession) -> int:
    now = datetime.utcnow()
    q = select(Reminder).where(
        and_(
            Reminder.status == ReminderStatus.SCHEDULED.value,
            Reminder.scheduled_time <= now,
        )
    )
    res = await session.execute(q)
    reminders: List[Reminder] = list(res.scalars().all())
    sent = 0
    for r in reminders:
        # Load appointment + client + master
        app = await session.get(Appointment, r.appointment_id)
        if not app or not app.client or not app.master:
            r.status = ReminderStatus.CANCELLED.value
            continue
        try:
            if r.reminder_type in (ReminderType.T_MINUS_24H.value, ReminderType.T_MINUS_2H.value):
                text = (
                    f"Напоминание о записи: {app.service.name}\n"
                    f"Время: {app.start_time.strftime('%d.%m.%Y %H:%M')}"
                )
                # Prefer Telegram: send to client if telegram_id known, else to master
                if app.client.telegram_id:
                    await bot.send_message(app.client.telegram_id, text)
                else:
                    await bot.send_message(app.master.telegram_id, f"Клиент без Telegram: {app.client.name} {app.client.phone}\n" + text)
            elif r.reminder_type == ReminderType.REACTIVATION.value:
                text = (
                    "Пора обновить запись? Нажмите, чтобы выбрать время."
                )
                if app.client.telegram_id:
                    await bot.send_message(app.client.telegram_id, text)
            r.status = ReminderStatus.SENT.value
            r.sent_at = now
            sent += 1
        except Exception as e:
            r.status = ReminderStatus.FAILED.value
            r.error_message = str(e)[:480]
    await session.flush()
    return sent
