"""Background tasks for checking incomplete appointments."""
from datetime import datetime, timezone
from typing import Dict, List

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from pytz import timezone as pytz_timezone

from database.repositories import AppointmentRepository, MasterRepository


async def notify_masters_incomplete_appointments(bot: Bot, session: AsyncSession) -> int:
    """
    Check all masters for incomplete past appointments and send notifications.
    Should run daily at 9:00 AM in each master's timezone.
    
    Returns:
        Number of masters notified
    """
    mrepo = MasterRepository(session)
    arepo = AppointmentRepository(session)
    
    # Get all masters
    masters = await mrepo.get_all()
    notified = 0
    
    for master in masters:
        try:
            # Get incomplete appointments for this master
            incomplete = await arepo.get_past_incomplete(master_id=master.id)
            
            if not incomplete:
                continue  # No incomplete appointments, skip
            
            # Prepare message
            tz_name = master.timezone or "Europe/Moscow"
            try:
                tz = pytz_timezone(tz_name)
            except Exception:
                tz = pytz_timezone("Europe/Moscow")
            
            # Group by date
            by_date: Dict[str, List] = {}
            for app in incomplete:
                # Convert to master's local time
                local_time = app.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                date_key = local_time.strftime('%d.%m.%Y')
                if date_key not in by_date:
                    by_date[date_key] = []
                by_date[date_key].append((app, local_time))
            
            # Build message
            lines = [
                "⚠️ <b>Незавершённые записи</b>\n",
                f"У вас есть {len(incomplete)} записей, которые нужно завершить:\n"
            ]
            
            # Add buttons for quick completion (limit to 5 most recent)
            buttons = []
            shown_count = 0
            
            for date_key in sorted(by_date.keys()):
                lines.append(f"\n<b>{date_key}</b>")
                for app, local_time in by_date[date_key]:
                    time_str = local_time.strftime('%H:%M')
                    service_name = app.service.name if app.service else "Услуга"
                    client_name = app.client.name if app.client else "Клиент"
                    lines.append(f"  • {time_str} — {service_name} — {client_name}")
                    
                    # Add quick complete button (max 5)
                    if shown_count < 5:
                        button_text = f"✓ {time_str} {client_name[:15]}"
                        buttons.append([InlineKeyboardButton(
                            text=button_text,
                            callback_data=f"complete_appt:{app.id}"
                        )])
                        shown_count += 1
            
            lines.append("\n💡 Нажмите кнопку ниже для быстрого завершения или откройте кабинет мастера.")
            
            message = "\n".join(lines)
            
            # Create keyboard if we have buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
            
            # Send notification
            await bot.send_message(master.telegram_id, message, parse_mode="HTML", reply_markup=keyboard)
            notified += 1
            
        except Exception as e:
            print(f"❌ Error notifying master {master.id}: {e}")
            continue
    
    return notified


async def check_and_notify_incomplete(bot: Bot, session: AsyncSession) -> None:
    """
    Wrapper function for APScheduler.
    Checks if it's 9 AM for any master and sends notifications.
    """
    try:
        count = await notify_masters_incomplete_appointments(bot, session)
        if count > 0:
            print(f"✅ Notified {count} masters about incomplete appointments")
    except Exception as e:
        print(f"❌ Error checking incomplete appointments: {e}")
