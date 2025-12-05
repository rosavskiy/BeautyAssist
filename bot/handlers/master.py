"""
Master handlers for business owner functionality.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from datetime import datetime, timezone, timedelta
from pytz import timezone as pytz_timezone
from database.base import async_session_maker
from database.repositories.master import MasterRepository
from database.repositories.service import ServiceRepository
from database.repositories.appointment import AppointmentRepository
from database.repositories.client import ClientRepository
from database.models.appointment import AppointmentStatus
from bot.config import settings, CITY_TZ_MAP

router = Router(name="master")

# Will be injected during registration
bot = None


def inject_bot(bot_instance):
    """Inject bot instance for this module."""
    global bot
    bot = bot_instance


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Show main menu with WebApp buttons and quick actions."""
    from bot.utils.webapp import build_webapp_url_direct, build_master_webapp_link
    
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть запись (WebApp)", web_app=WebAppInfo(url=build_webapp_url_direct(master)))],
            [InlineKeyboardButton(text="Открыть кабинет (Master)", web_app=WebAppInfo(url=build_master_webapp_link(master)))],
            [
                InlineKeyboardButton(text="Записи: ближайший день", callback_data="next_day"),
                InlineKeyboardButton(text="Записи: ближайшая неделя", callback_data="next_week"),
            ],
        ])
        await message.answer("Главное меню", reply_markup=kb)


@router.message(Command("services"))
async def cmd_services(message: Message):
    """Open services management Mini App."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        # Create WebApp button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        
        # Use webapp_base_url from settings or fallback to localhost for development
        base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
        webapp_url = f"{base_url}/webapp/master/services.html?mid={master.id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Управление услугами",
                web_app=WebAppInfo(url=webapp_url)
            )]
        ])
        
        await message.answer(
            "Управляйте вашими услугами через удобный интерфейс 👇",
            reply_markup=keyboard
        )


@router.message(Command("appointments"))
async def cmd_appointments(message: Message):
    """Show today's appointments."""
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        now_local = datetime.now(timezone.utc).astimezone(tz)
        start_local = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0))
        end_local = start_local + timedelta(days=1)
        start_day = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_day = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        apps = await arepo.get_by_master(master.id, start_date=start_day, end_date=end_day)
        if not apps:
            return await message.answer("На сегодня записей нет")
        lines = ["Записи на сегодня:"]
        for a in sorted(apps, key=lambda x: x.start_time):
            try:
                service = await srepo.get_by_id(a.service_id)
            except Exception:
                service = None
            client = await crepo.get_by_id(a.client_id)
            local_start = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
            when = local_start.strftime('%H:%M')
            svc_name = service.name if service else "Услуга"
            lines.append(f"- {when} {svc_name} — {client.name} ({client.phone})")
        await message.answer("\n".join(lines))


@router.message(Command("clients"))
async def cmd_clients(message: Message):
    """Open clients management Mini App."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        # Create WebApp button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        
        # Use webapp_base_url from settings or fallback to localhost for development
        base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
        webapp_url = f"{base_url}/webapp/master/clients.html?mid={master.id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="👥 Управление клиентами",
                web_app=WebAppInfo(url=webapp_url)
            )]
        ])
        
        await message.answer(
            "Управляйте вашими контактами через удобный интерфейс 👇",
            reply_markup=keyboard
        )


@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    """Set default work schedule."""
    from bot.handlers.onboarding import show_setup_complete_message
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        was_empty = not master.work_schedule
        
        if not master.work_schedule:
            master.work_schedule = {
                "monday": [["10:00", "19:00"]],
                "tuesday": [["10:00", "19:00"]],
                "wednesday": [["10:00", "19:00"]],
                "thursday": [["10:00", "19:00"]],
                "friday": [["10:00", "19:00"]],
                "saturday": [["10:00", "17:00"]],
                "sunday": [["10:00", "17:00"]],
            }
            await mrepo.update(master)
            await session.commit()
        
        await message.answer("✅ График сохранён по умолчанию (ПН-ПТ 10-19, СБ-ВС 10-17).\nНастроить детально можно в кабинете мастера.")
        
        # If this was during onboarding (city set but no schedule), show completion
        if was_empty and master.city:
            # Get fresh master after commit
            updated_master = await mrepo.get_by_telegram_id(message.from_user.id)
            await show_setup_complete_message(message, updated_master)


@router.message(Command("city"))
async def cmd_city(message: Message):
    """Set or change city and timezone."""
    parts = message.text.split(maxsplit=1)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        if len(parts) < 2:
            # Show inline keyboard with city selection
            rows = []
            cities = list(CITY_TZ_MAP.keys())
            for i in range(0, len(cities), 3):
                chunk = cities[i:i+3]
                rows.append([InlineKeyboardButton(text=c, callback_data=f"set_city:{c}") for c in chunk])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
            return await message.answer("Выберите город:", reply_markup=kb)
        city = parts[1].strip()
        tz = CITY_TZ_MAP.get(city, master.timezone or "Europe/Moscow")
        master.city = city
        master.timezone = tz
        await mrepo.update(master)
        await session.commit()
        await message.answer(f"Город сохранён: {city}. Таймзона: {tz}.")


@router.callback_query(F.data.startswith("set_city:"))
async def cb_set_city(call: CallbackQuery):
    """Handle city selection from inline keyboard."""
    city = call.data.split(":", 1)[1]
    tz = CITY_TZ_MAP.get(city)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Сначала отправьте /start", show_alert=True)
            return
        if not tz:
            await call.answer("Неизвестный город", show_alert=True)
            return
        master.city = city
        master.timezone = tz
        await mrepo.update(master)
        await session.commit()
    try:
        await call.message.edit_text(f"Город сохранён: {city}. Таймзона: {tz}.")
    except Exception:
        await call.message.answer(f"Город сохранён: {city}. Таймзона: {tz}.")
    await call.answer()




def register_handlers(dp):
    """Register master handlers."""
    dp.include_router(router)
