"""
Appointment management handlers for callback queries.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timezone, timedelta
from pytz import timezone as pytz_timezone
from database.base import async_session_maker
from database.repositories.master import MasterRepository
from database.repositories.appointment import AppointmentRepository
from database.repositories.client import ClientRepository
from database.repositories.service import ServiceRepository
from database.repositories.reminder import ReminderRepository
from database.models.appointment import AppointmentStatus
from database.models.service import Service

router = Router(name="appointments")

# Will be injected during registration
bot = None


def inject_bot(bot_instance):
    """Inject bot instance for this module."""
    global bot
    bot = bot_instance


def _format_rub(amount: int) -> str:
    """Format amount as rubles."""
    return f"{amount:,}".replace(",", " ") + " ₽"


async def _load_services_map(srepo: ServiceRepository, service_ids: set[int]) -> dict[int, Service]:
    """Load services by IDs into a dict."""
    result: dict[int, Service] = {}
    for sid in service_ids:
        svc = await srepo.get_by_id(sid)
        if svc:
            result[sid] = svc
    return result


@router.callback_query(F.data == "next_day")
async def cb_next_day(call: CallbackQuery):
    """Show appointments for next upcoming day."""
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            return await call.message.answer("Нажмите /start для регистрации")
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc
        end_utc = now_utc + timedelta(days=8)
        apps = await arepo.get_by_master(master.id, start_date=start_utc.replace(tzinfo=None), end_date=end_utc.replace(tzinfo=None))
        apps = [a for a in apps if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)]
        if not apps:
            return await call.message.answer("В ближайшие дни записей нет")
        by_day: dict[datetime.date, list] = {}
        for a in apps:
            d_local = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz).date()
            by_day.setdefault(d_local, []).append(a)
        today_local = now_utc.astimezone(tz).date()
        next_dates = sorted([d for d in by_day.keys() if d >= today_local])
        if not next_dates:
            return await call.message.answer("В ближайшие дни записей нет")
        target = next_dates[0]
        day_apps = sorted(by_day[target], key=lambda x: x.start_time)
        svc_map = await _load_services_map(srepo, set(a.service_id for a in day_apps))
        lines = [f"Записи на {target.strftime('%d.%m.%Y')}:"]
        day_sum = 0
        for a in day_apps:
            svc = svc_map.get(a.service_id)
            client = await crepo.get_by_id(a.client_id)
            when = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz).strftime('%H:%M')
            price = (svc.price if svc and getattr(svc, 'price', None) is not None else 0)
            day_sum += price
            svc_name = svc.name if svc else "Услуга"
            lines.append(f"- {when} {svc_name} — {client.name} ({_format_rub(price)})")
        lines.append("")
        lines.append(f"Прогноз за день: {_format_rub(day_sum)}")
        await call.message.answer("\n".join(lines))
        await call.answer()


@router.callback_query(F.data == "next_week")
async def cb_next_week(call: CallbackQuery):
    """Show appointments for next 7 days."""
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            return await call.message.answer("Нажмите /start для регистрации")
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        now_local = datetime.now(timezone.utc).astimezone(tz)
        start_local = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0))
        end_local = start_local + timedelta(days=7)
        start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        apps = await arepo.get_by_master(master.id, start_date=start_utc, end_date=end_utc)
        apps = [a for a in apps if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)]
        if not apps:
            await call.message.answer("В ближайшую неделю записей нет")
            return await call.answer()
        # Group by local day
        by_day: dict[datetime.date, list] = {}
        for a in apps:
            d_local = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz).date()
            by_day.setdefault(d_local, []).append(a)
        all_dates = sorted(by_day.keys())
        svc_ids = set(a.service_id for a in apps)
        svc_map = await _load_services_map(srepo, svc_ids)
        lines = ["Записи на ближайшую неделю:"]
        week_sum = 0
        for d in all_dates:
            day_apps = sorted(by_day[d], key=lambda x: x.start_time)
            lines.append("")
            lines.append(d.strftime('%d.%m.%Y (%A)').replace('Monday','Понедельник').replace('Tuesday','Вторник').replace('Wednesday','Среда').replace('Thursday','Четверг').replace('Friday','Пятница').replace('Saturday','Суббота').replace('Sunday','Воскресенье'))
            day_sum = 0
            for a in day_apps:
                svc = svc_map.get(a.service_id)
                client = await crepo.get_by_id(a.client_id)
                when = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz).strftime('%H:%M')
                price = (svc.price if svc and getattr(svc, 'price', None) is not None else 0)
                day_sum += price
                svc_name = svc.name if svc else "Услуга"
                lines.append(f"- {when} {svc_name} — {client.name} ({_format_rub(price)})")
            lines.append(f"Итого за день: {_format_rub(day_sum)}")
            week_sum += day_sum
        lines.append("")
        lines.append(f"Прогноз за неделю: {_format_rub(week_sum)}")
        await call.message.answer("\n".join(lines))
        await call.answer()


@router.callback_query(F.data.startswith("complete_appt:"))
async def cb_complete_appointment(call: CallbackQuery):
    """Quick complete appointment from notification."""
    try:
        appointment_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Ошибка: неверный ID записи", show_alert=True)
        return
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Мастер не найден", show_alert=True)
            return
        
        appointment = await arepo.get_by_id(appointment_id)
        if not appointment or appointment.master_id != master.id:
            await call.answer("Запись не найдена", show_alert=True)
            return
        
        # Ask for confirmation with payment buttons
        client = await crepo.get_by_id(appointment.client_id)
        service = await srepo.get_by_id(appointment.service_id)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Пришёл", callback_data=f"confirm_came:{appointment_id}"),
                InlineKeyboardButton(text="❌ Не пришёл", callback_data=f"confirm_noshow:{appointment_id}")
            ],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_action")]
        ])
        
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        local_time = appointment.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
        
        msg = (
            f"📋 <b>Завершить запись?</b>\n\n"
            f"Клиент: {client.name}\n"
            f"Услуга: {service.name if service else 'Услуга'}\n"
            f"Время: {local_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Клиент пришёл?"
        )
        
        try:
            await call.message.edit_text(msg, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await call.message.answer(msg, reply_markup=kb, parse_mode="HTML")
        
        await call.answer()


@router.callback_query(F.data.startswith("confirm_came:"))
async def cb_confirm_came(call: CallbackQuery):
    """Mark appointment as completed with payment."""
    try:
        appointment_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Ошибка", show_alert=True)
        return
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Мастер не найден", show_alert=True)
            return
        
        appointment = await arepo.get_by_id(appointment_id)
        if not appointment or appointment.master_id != master.id:
            await call.answer("Запись не найдена", show_alert=True)
            return
        
        service = await srepo.get_by_id(appointment.service_id)
        client = await crepo.get_by_id(appointment.client_id)
        
        # Complete appointment
        appointment.status = AppointmentStatus.COMPLETED.value
        appointment.is_completed = True
        appointment.payment_amount = service.price if service else 0
        
        # Update client stats
        if client:
            client.total_visits += 1
            client.total_spent += appointment.payment_amount
            client.last_visit = appointment.start_time
            await crepo.update(client)
        
        await arepo.update(appointment)
        await session.commit()
        
        msg = (
            f"✅ <b>Запись завершена</b>\n\n"
            f"Клиент: {client.name}\n"
            f"Оплата: {appointment.payment_amount} ₽"
        )
        
        try:
            await call.message.edit_text(msg, parse_mode="HTML")
        except Exception:
            await call.message.answer(msg, parse_mode="HTML")
        
        await call.answer("Запись завершена ✅")


@router.callback_query(F.data.startswith("confirm_noshow:"))
async def cb_confirm_noshow(call: CallbackQuery):
    """Mark appointment as no-show."""
    try:
        appointment_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Ошибка", show_alert=True)
        return
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Мастер не найден", show_alert=True)
            return
        
        appointment = await arepo.get_by_id(appointment_id)
        if not appointment or appointment.master_id != master.id:
            await call.answer("Запись не найдена", show_alert=True)
            return
        
        client = await crepo.get_by_id(appointment.client_id)
        
        # Mark as no-show
        appointment.status = AppointmentStatus.NO_SHOW.value
        appointment.is_completed = True
        await arepo.update(appointment)
        await session.commit()
        
        msg = f"❌ <b>Отмечено: клиент не пришёл</b>\n\nКлиент: {client.name}"
        
        try:
            await call.message.edit_text(msg, parse_mode="HTML")
        except Exception:
            await call.message.answer(msg, parse_mode="HTML")
        
        await call.answer("Отмечено как неявка")


@router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(call: CallbackQuery):
    """Cancel action."""
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("Отменено")


@router.callback_query(F.data.startswith("client_confirm:"))
async def cb_client_confirm_appointment(call: CallbackQuery):
    """Client confirms they will attend the appointment."""
    try:
        appointment_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    
    try:
        async with async_session_maker() as session:
            arepo = AppointmentRepository(session)
            app = await arepo.get_by_id(appointment_id)
            
            if not app:
                await call.answer("❌ Запись не найдена", show_alert=True)
                return
            
            # Update status to confirmed
            app.status = AppointmentStatus.CONFIRMED.value
            session.add(app)
            await session.commit()
            
            # Notify client
            await call.message.edit_text(
                f"✅ <b>Запись подтверждена!</b>\n\n"
                f"Спасибо! Ждём вас {app.start_time.strftime('%d.%m.%Y в %H:%M')}",
                parse_mode="HTML"
            )
            
            # Notify master
            if app.master and app.master.telegram_id:
                try:
                    master_tz = pytz_timezone(app.master.timezone or "Europe/Moscow")
                    local_time = app.start_time.replace(tzinfo=timezone.utc).astimezone(master_tz)
                    service_name = app.service.name if app.service else "Услуга"
                    
                    await bot.send_message(
                        app.master.telegram_id,
                        f"✅ <b>Клиент подтвердил запись!</b>\n\n"
                        f"👤 {app.client.name}\n"
                        f"📱 {app.client.phone}\n"
                        f"📋 {service_name}\n"
                        f"📅 {local_time.strftime('%d.%m.%Y в %H:%M')}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            
            await call.answer("✅ Запись подтверждена!")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("client_cancel:"))
async def cb_client_cancel_appointment(call: CallbackQuery):
    """Client wants to cancel the appointment."""
    try:
        appointment_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    
    try:
        async with async_session_maker() as session:
            arepo = AppointmentRepository(session)
            app = await arepo.get_by_id(appointment_id)
            
            if not app:
                await call.answer("❌ Запись не найдена", show_alert=True)
                return
            
            # Show confirmation with reason buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Подтвердить отмену",
                    callback_data=f"client_cancel_confirm:{appointment_id}"
                )],
                [InlineKeyboardButton(
                    text="Оставить запись",
                    callback_data="cancel_action"
                )]
            ])
            
            await call.message.edit_text(
                f"⚠️ <b>Отмена записи</b>\n\n"
                f"Вы уверены, что хотите отменить запись на {app.start_time.strftime('%d.%m.%Y в %H:%M')}?\n\n"
                f"Пожалуйста, предупредите мастера заранее, чтобы он мог освободить время для других клиентов.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(F.data.startswith("client_cancel_confirm:"))
async def cb_client_cancel_confirm(call: CallbackQuery):
    """Client confirmed cancellation."""
    try:
        appointment_id = int(call.data.split(":")[1])
    except (IndexError, ValueError):
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    
    try:
        async with async_session_maker() as session:
            arepo = AppointmentRepository(session)
            app = await arepo.get_by_id(appointment_id)
            
            if not app:
                await call.answer("❌ Запись не найдена", show_alert=True)
                return
            
            # Cancel appointment
            app.status = AppointmentStatus.CANCELLED.value
            session.add(app)
            await session.commit()
            
            # Cancel reminders
            reminder_repo = ReminderRepository(session)
            await reminder_repo.cancel_appointment_reminders(appointment_id)
            await session.commit()
            
            # Notify client
            await call.message.edit_text(
                f"❌ <b>Запись отменена</b>\n\n"
                f"Запись на {app.start_time.strftime('%d.%m.%Y в %H:%M')} отменена.\n"
                f"Будем рады видеть вас в другое время!",
                parse_mode="HTML"
            )
            
            # Notify master
            if app.master and app.master.telegram_id:
                try:
                    master_tz = pytz_timezone(app.master.timezone or "Europe/Moscow")
                    local_time = app.start_time.replace(tzinfo=timezone.utc).astimezone(master_tz)
                    service_name = app.service.name if app.service else "Услуга"
                    
                    await bot.send_message(
                        app.master.telegram_id,
                        f"❌ <b>Клиент отменил запись</b>\n\n"
                        f"👤 {app.client.name}\n"
                        f"📱 {app.client.phone}\n"
                        f"📋 {service_name}\n"
                        f"📅 {local_time.strftime('%d.%m.%Y в %H:%M')}\n\n"
                        f"Время освободилось для других клиентов.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            
            await call.answer("Запись отменена")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


def register_handlers(dp):
    """Register appointment handlers."""
    dp.include_router(router)
