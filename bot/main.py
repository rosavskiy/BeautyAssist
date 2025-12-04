"""Bot entrypoint with Telegram WebApp + API (aiohttp) + polling.
Note: For production, prefer webhook + HTTPS. For development, polling is OK.
"""
import datetime
from datetime import timezone
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery, MenuButtonWebApp, BotCommand, BotCommandScopeChat, MenuButtonDefault
from aiogram import types
from pytz import timezone as pytz_timezone

from bot.config import settings
from database import async_session_maker, init_db
from database.repositories import MasterRepository, ServiceRepository, ClientRepository, AppointmentRepository, ReminderRepository
from database.models import Master, Service, AppointmentStatus
from bot.keyboards import get_main_menu_keyboard
from bot.utils.time_utils import get_available_dates, parse_work_schedule, generate_time_slots, parse_time, generate_half_hour_slots
from services.scheduler import create_appointment_reminders

CITY_TZ_MAP = {
    "Москва": "Europe/Moscow",
    "Санкт-Петербург": "Europe/Moscow",
    "Екатеринбург": "Asia/Yekaterinburg",
    "Новосибирск": "Asia/Novosibirsk",
    "Красноярск": "Asia/Krasnoyarsk",
    "Владивосток": "Asia/Vladivostok",
    "Самара": "Europe/Samara",
    "Саратов": "Europe/Saratov",
}

# ========== Aiogram Bot ==========
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


def build_webapp_link(master: Master, service_id: Optional[int] = None) -> str:
    """Build bot link that will show WebApp button for booking."""
    if not settings.bot_username:
        return ""
    # Use bot deep link with start parameter
    # When user opens this link, bot will show WebApp button
    params = master.referral_code
    if service_id:
        params += f"_{service_id}"  # Use underscore as separator
    return f"https://t.me/{settings.bot_username}?start={params}"


def build_webapp_url_direct(master: Master, service_id: Optional[int] = None) -> str:
    """Build direct WebApp URL for WebApp button."""
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    if base.endswith("/webapp"):
        base_webapp = base
    else:
        base_webapp = base + "/webapp"
    params = f"?code={master.referral_code}"
    if service_id:
        params += f"&service={service_id}"
    return f"{base_webapp}/index.html{params}"


def build_client_appointments_url(master: Master) -> str:
    """Build WebApp URL for client to view their appointments."""
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    if base.endswith("/webapp"):
        base_webapp = base
    else:
        base_webapp = base + "/webapp"
    return f"{base_webapp}/appointments.html?code={master.referral_code}"


def build_master_webapp_link(master: Master) -> str:
    if not settings.webapp_base_url:
        return ""
    base = str(settings.webapp_base_url).rstrip("/")
    # If WEBAPP_BASE_URL ends with /webapp, point to /webapp-master
    if base.endswith("/webapp"):
        base_master = base[:-7] + "/webapp-master"
    else:
        base_master = base + "/webapp-master"
    params = f"?mid={master.telegram_id}"
    return f"{base_master}/master.html{params}"


async def ensure_default_services(session, master: Master):
    """Create a couple of default services if none exist."""
    srepo = ServiceRepository(session)
    existing = await srepo.get_all_by_master(master.id, active_only=False)
    if existing:
        return
    # Create basic demo services
    await srepo.create(master.id, name="Маникюр", duration_minutes=90, price=1500)
    await srepo.create(master.id, name="Коррекция бровей", duration_minutes=60, price=1200)
    await session.commit()


@dp.message(CommandStart())
async def on_start(message: Message, command: CommandObject):
    # Check if this is a client booking link (has start parameter)
    start_param = command.args if command else None
    
    if start_param:
        # Client clicked booking link: show WebApp button
        # Parse referral_code and optional service_id
        parts = start_param.split('_')
        referral_code = parts[0]
        service_id = int(parts[1]) if len(parts) > 1 else None
        
        async with async_session_maker() as session:
            master = await MasterRepository(session).get_by_referral_code(referral_code)
            if not master:
                return await message.answer("Мастер не найден")
            
            webapp_url = build_webapp_url_direct(master, service_id)
            appointments_url = build_client_appointments_url(master)
            if not webapp_url:
                return await message.answer("Ошибка конфигурации")
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Записаться к мастеру", web_app=WebAppInfo(url=webapp_url))],
                [InlineKeyboardButton(text="📋 Мои записи", web_app=WebAppInfo(url=appointments_url))]
            ])
            await message.answer(
                f"👋 Здравствуйте!\n\n"
                f"Нажмите кнопку ниже, чтобы выбрать услугу и время записи.",
                reply_markup=kb
            )
            # Remove menu commands for clients (clear bot commands)
            try:
                await bot.set_my_commands(commands=[], scope=types.BotCommandScopeChat(chat_id=message.chat.id))
                await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=types.MenuButtonDefault())
            except Exception:
                pass
            return
    
    # Master's /start command
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        is_new_master = False
        if not master:
            is_new_master = True
            name = (message.from_user.full_name or "Мастер").strip()
            master = await mrepo.create(
                telegram_id=message.from_user.id,
                name=name,
                telegram_username=message.from_user.username,
            )
            await session.commit()
        
        # Check if initial setup is needed
        needs_setup = not master.city or not master.timezone or not master.work_schedule
        
        if is_new_master or needs_setup:
            # Start onboarding flow
            await message.answer(
                "👋 <b>Добро пожаловать в BeautyAssist!</b>\n\n"
                "Я помогу вам автоматизировать запись клиентов и управление записями.\n\n"
                "Давайте настроим ваш профиль за несколько шагов:"
            )
            
            # Step 1: City/Timezone
            if not master.city or not master.timezone:
                rows = []
                cities = list(CITY_TZ_MAP.keys())
                for i in range(0, len(cities), 2):
                    chunk = cities[i:i+2]
                    rows.append([InlineKeyboardButton(text=c, callback_data=f"setup_city:{c}") for c in chunk])
                kb = InlineKeyboardMarkup(inline_keyboard=rows)
                return await message.answer(
                    "📍 <b>Шаг 1/2: Выберите ваш город</b>\n\n"
                    "Это нужно для правильного отображения времени записей:",
                    reply_markup=kb
                )
            
            # Step 2: Work schedule
            if not master.work_schedule:
                return await message.answer(
                    "📅 <b>Шаг 2/2: Установите график работы</b>\n\n"
                    "Отправьте график в формате:\n"
                    "<code>ПН-ПТ 10:00-19:00; СБ-ВС 10:00-17:00</code>\n\n"
                    "Или используйте команду /schedule для установки базового графика (ПН-ПТ 10-19, СБ-ВС 10-17)."
                )
        
        # Seed default services if empty
        await ensure_default_services(session, master)
        link_client = build_webapp_link(master)
        link_master = build_master_webapp_link(master)
        schedule_str = format_work_schedule(master.work_schedule)
        text = (
            "✅ <b>Профиль настроен! Можно работать!</b>\n\n"
            "📋 <b>Ваши настройки:</b>\n"
            f"• Город: {master.city}\n"
            f"• График: {schedule_str}\n\n"
            "🔗 <b>Ссылка для клиентов</b> (отправьте им):\n"
            f"{link_client or 'Укажите BOT_USERNAME в .env'}\n\n"
            "📱 <b>Команды бота:</b>\n"
            "• /menu — открыть меню с кнопками WebApp\n"
            "• /services — список услуг (добавляйте: Название;Цена;ДлительностьМин)\n"
            "• /appointments — записи на сегодня\n"
            "• /clients — список клиентов\n"
            "• /schedule — изменить график работы\n"
            "• /city — изменить город/таймзону\n"
        )
        await message.answer(text)
        # Set chat menu WebApp button (blue near input) to Master cabinet
        try:
            master_url = build_master_webapp_link(master)
            if master_url:
                await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(text="Кабинет", web_app=WebAppInfo(url=master_url)))
        except Exception:
            pass
        # Register bot commands so they show in client hints
        try:
            await bot.set_my_commands(commands=[
                BotCommand(command="start", description="Приветствие и ссылки"),
                BotCommand(command="menu", description="Кнопки WebApp"),
                BotCommand(command="services", description="Список услуг"),
                BotCommand(command="appointments", description="Записи на сегодня"),
                BotCommand(command="clients", description="Список клиентов"),
                BotCommand(command="schedule", description="Базовый график"),
                BotCommand(command="city", description="Выбрать город/таймзону"),
            ])
        except Exception:
            pass


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
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


@dp.message(Command("services"))
async def cmd_services(message: Message):
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        srepo = ServiceRepository(session)
        services = await srepo.get_all_by_master(master.id, active_only=False)
        if not services:
            return await message.answer("Услуги не добавлены. Отправьте в формате: Название;Цена;Длительность(мин). Пример: Маникюр;1500;90")
        lines = [f"Услуги ({len(services)}):"]
        for s in services:
            lines.append(f"- {s.name}: {s.price} ₽, {s.duration_minutes} мин")
        await message.answer("\n".join(lines))


@dp.message(Command("appointments"))
async def cmd_appointments(message: Message):
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
@dp.message(Command("clients"))
async def cmd_clients(message: Message):
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        # simple list via relationship or repository
        # Use direct query through repository if available
        # Here, load via appointments repo for minimal deps
        from sqlalchemy import select
        from database.models.client import Client
        res = await session.execute(select(Client).where(Client.master_id == master.id).order_by(Client.name))
        clients = res.scalars().all()
        if not clients:
            return await message.answer("Клиенты пока не добавлены")
        lines = [f"Клиенты ({len(clients)}):"]
        for c in clients[:200]:
            tg = f" @{c.telegram_username}" if c.telegram_username else ""
            lines.append(f"- {c.name}{tg} — {c.phone}")
        await message.answer("\n".join(lines))


def _format_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


async def _load_services_map(srepo: ServiceRepository, service_ids: set[int]) -> dict[int, Service]:
    result: dict[int, Service] = {}
    for sid in service_ids:
        svc = await srepo.get_by_id(sid)
        if svc:
            result[sid] = svc
    return result


@dp.callback_query(F.data == "next_day")
async def cb_next_day(call: CallbackQuery):
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


@dp.callback_query(F.data == "next_week")
async def cb_next_week(call: CallbackQuery):
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


@dp.message(~F.text.startswith("/") & F.text.contains(";"))
async def add_service_freeform(message: Message):
    parts = [p.strip() for p in message.text.split(";")]
    if len(parts) != 3:
        return
    name, price_s, dur_s = parts
    try:
        price = int(price_s)
        duration = int(dur_s)
    except ValueError:
        return await message.answer("Ошибка: цена и длительность должны быть числами")
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        # Simple freemium guard: max services
        count = await srepo.count_by_master(master.id, active_only=False)
        if not master.is_premium and count >= settings.free_max_services:
            return await message.answer("На бесплатном тарифе лимит услуг исчерпан. Оформите подписку.")
        await srepo.create(master.id, name=name, duration_minutes=duration, price=price)
        await session.commit()
        await message.answer("Услуга добавлена ✅")


@dp.message(Command("schedule"))
async def cmd_schedule(message: Message):
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


@dp.message(Command("city"))
async def cmd_city(message: Message):
    """Установка города и таймзоны мастера."""
    parts = message.text.split(maxsplit=1)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        if len(parts) < 2:
            # Показать инлайн-клавиатуру выбора города
            rows = []
            cities = list(CITY_TZ_MAP.keys())
            # по 2-3 кнопки в ряд
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


@dp.callback_query(F.data.startswith("set_city:"))
async def cb_set_city(call: CallbackQuery):
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


@dp.callback_query(F.data.startswith("setup_city:"))
async def cb_setup_city(call: CallbackQuery):
    """Handler for city selection during onboarding."""
    city = call.data.split(":", 1)[1]
    tz = CITY_TZ_MAP.get(city)
    
    needs_schedule = False
    updated_master = None
    
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
        
        # Check if work schedule is set
        needs_schedule = not master.work_schedule
        
        # Get fresh copy for showing completion message
        updated_master = await mrepo.get_by_telegram_id(call.from_user.id)
    
    try:
        await call.message.edit_text(f"✅ Город установлен: {city}")
    except Exception:
        pass
    
    await call.answer()
    
    if needs_schedule:
        # Continue to next step
        await call.message.answer(
            "📅 <b>Шаг 2/2: Установите график работы</b>\n\n"
            "Отправьте график в формате:\n"
            "<code>ПН-ПТ 10:00-19:00; СБ-ВС 10:00-17:00</code>\n\n"
            "Или используйте команду /schedule для установки базового графика (ПН-ПТ 10-19, СБ-ВС 10-17)."
        )
    else:
        # Setup complete, show final message
        await show_setup_complete_message(call.message, updated_master)


def format_work_schedule(schedule: dict) -> str:
    """Format work schedule dict to readable string."""
    if not schedule:
        return "не установлен"
    
    day_names = {
        'monday': 'ПН',
        'tuesday': 'ВТ',
        'wednesday': 'СР',
        'thursday': 'ЧТ',
        'friday': 'ПТ',
        'saturday': 'СБ',
        'sunday': 'ВС'
    }
    
    # Group consecutive days with same hours
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    groups = []
    current_group = None
    
    for day in days_order:
        hours = schedule.get(day)
        if not hours:
            if current_group:
                groups.append(current_group)
                current_group = None
            continue
        
        hours_str = ', '.join([f"{h[0]}-{h[1]}" for h in hours])
        
        if current_group and current_group['hours'] == hours_str:
            current_group['days'].append(day_names[day])
        else:
            if current_group:
                groups.append(current_group)
            current_group = {'days': [day_names[day]], 'hours': hours_str}
    
    if current_group:
        groups.append(current_group)
    
    # Format groups
    result = []
    for group in groups:
        days_str = '-'.join([group['days'][0], group['days'][-1]]) if len(group['days']) > 1 else group['days'][0]
        result.append(f"{days_str} {group['hours']}")
    
    return '; '.join(result) if result else "не установлен"


async def show_setup_complete_message(message: Message, master: Master):
    """Show completion message after onboarding."""
    link_client = build_webapp_link(master)
    link_master = build_master_webapp_link(master)
    
    # Seed default services if needed
    async with async_session_maker() as session:
        await ensure_default_services(session, master)
    
    schedule_str = format_work_schedule(master.work_schedule)
    
    text = (
        "✅ <b>Профиль настроен! Можно работать!</b>\n\n"
        "📋 <b>Ваши настройки:</b>\n"
        f"• Город: {master.city}\n"
        f"• График: {schedule_str}\n\n"
        "🔗 <b>Ссылка для клиентов</b> (отправьте им):\n"
        f"{link_client or 'Укажите BOT_USERNAME в .env'}\n\n"
        "📱 <b>Команды бота:</b>\n"
        "• /menu — открыть меню с кнопками WebApp\n"
        "• /services — список услуг (добавляйте: Название;Цена;ДлительностьМин)\n"
        "• /appointments — записи на сегодня\n"
        "• /clients — список клиентов\n"
        "• /schedule — изменить график работы\n"
        "• /city — изменить город/таймзону\n"
    )
    await message.answer(text)
    
    # Set chat menu WebApp button
    try:
        master_url = build_master_webapp_link(master)
        if master_url:
            await bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(text="Кабинет", web_app=WebAppInfo(url=master_url))
            )
    except Exception:
        pass
    
    # Register bot commands
    try:
        await bot.set_my_commands(commands=[
            BotCommand(command="start", description="Приветствие и ссылки"),
            BotCommand(command="menu", description="Кнопки WebApp"),
            BotCommand(command="services", description="Список услуг"),
            BotCommand(command="appointments", description="Записи на сегодня"),
            BotCommand(command="clients", description="Список клиентов"),
            BotCommand(command="schedule", description="График работы"),
            BotCommand(command="city", description="Выбрать город/таймзону"),
        ], scope=BotCommandScopeChat(chat_id=message.chat.id))
    except Exception:
        pass


@dp.callback_query(F.data.startswith("complete_appt:"))
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


@dp.callback_query(F.data.startswith("confirm_came:"))
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


@dp.callback_query(F.data.startswith("confirm_noshow:"))
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


@dp.callback_query(F.data == "cancel_action")
async def cb_cancel_action(call: CallbackQuery):
    """Cancel action."""
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer("Отменено")


@dp.callback_query(F.data.startswith("client_confirm:"))
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


@dp.callback_query(F.data.startswith("client_cancel:"))
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


@dp.callback_query(F.data.startswith("client_cancel_confirm:"))
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
            from database.repositories import ReminderRepository
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


# ========== Aiohttp App (API + Webhook + Static) ==========

routes = web.RouteTableDef()


@routes.get("/health")
async def health(_):
    from datetime import timezone
    return web.json_response({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@routes.get("/api/master/appointments")
async def api_master_appointments(request: web.Request):
    mid = request.query.get("mid")
    date_str = request.query.get("date")  # Optional YYYY-MM-DD
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        
        # Determine target date
        if date_str:
            # Date comes as YYYY-MM-DD from frontend
            # Interpret it in master's timezone (not UTC)
            try:
                year, month, day = map(int, date_str.split('-'))
                # Create date at midnight in master's local timezone
                target_date = tz.localize(datetime(year, month, day, 0, 0))
            except Exception as e:
                return web.json_response({"error": f"invalid date format, use YYYY-MM-DD: {str(e)}"}, status=400)
        else:
            # Default to today in master's timezone
            now_local = datetime.now(timezone.utc).astimezone(tz)
            target_date = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0))
        
        start_local = target_date
        end_local = start_local + timedelta(days=1)
        start_day = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_day = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        
        # Fetch appointments for the selected day
        from sqlalchemy import select
        from database.models.appointment import Appointment
        stmt = select(Appointment).where(
            Appointment.master_id == master.id,
            Appointment.start_time >= start_day,
            Appointment.start_time < end_day
        ).order_by(Appointment.start_time)
        res = await session.execute(stmt)
        apps = res.scalars().all()
        
        result = []
        for a in apps:
            service = await srepo.get_by_id(a.service_id)
            client = await crepo.get_by_id(a.client_id)
            start_local = a.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
            end_local = a.end_time.replace(tzinfo=timezone.utc).astimezone(tz)
            is_past = a.start_time.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
            result.append({
                "id": a.id,
                "service": service.name if service else "",
                "service_id": a.service_id,
                "service_price": service.price if service else 0,
                "client": {"name": client.name, "phone": client.phone, "username": client.telegram_username, "telegram_id": client.telegram_id},
                "start": start_local.isoformat(),
                "end": end_local.isoformat(),
                "status": a.status,
                "is_completed": a.is_completed,
                "is_past": is_past
            })
        # Expose simple work schedule for frontend highlighting
        return web.json_response({
            "referral_code": master.referral_code,
            "appointments": result,
            "work_schedule": (lambda ws: {**ws, "days_off_dates": ws.get("days_off_dates", []), "days_off": ws.get("days_off", ws.get("non_working_days", []))})(master.work_schedule or {})
        })


@routes.get("/api/master/schedule")
async def api_master_schedule(request: web.Request):
    mid = request.query.get("mid")
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        return web.json_response({
            "timezone": master.timezone,
            "city": master.city,
            "work_schedule": (lambda ws: {**ws, "days_off_dates": ws.get("days_off_dates", []), "days_off": ws.get("days_off", ws.get("non_working_days", []))})(master.work_schedule or {})
        })


@routes.get("/api/master/clients")
async def api_master_clients(request: web.Request):
    mid = request.query.get("mid")
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        from sqlalchemy import select
        from database.models.client import Client
        res = await session.execute(select(Client).where(Client.master_id == master.id).order_by(Client.name))
        clients = res.scalars().all()
        return web.json_response([
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "username": c.telegram_username,
                "last_visit": c.last_visit.isoformat() if c.last_visit else None,
                "total_visits": c.total_visits,
                "total_spent": c.total_spent,
            } for c in clients
        ])


@routes.get("/api/services")
async def api_services(request: web.Request):
    code = request.query.get("code")
    if not code:
        return web.json_response({"error": "code is required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        services = await srepo.get_all_by_master(master.id, active_only=True)
        return web.json_response([
            {"id": s.id, "name": s.name, "price": s.price, "duration": s.duration_minutes}
            for s in services
        ])


@routes.get("/api/client/info")
async def api_client_info(request: web.Request):
    """Get client info by telegram_id to prefill booking form."""
    code = request.query.get("code")
    telegram_id_s = request.query.get("telegram_id")
    if not code or not telegram_id_s:
        return web.json_response({"error": "code and telegram_id required"}, status=400)
    try:
        telegram_id = int(telegram_id_s)
    except ValueError:
        return web.json_response({"error": "invalid telegram_id"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        from sqlalchemy import select
        from database.models.client import Client
        result = await session.execute(
            select(Client).where(
                Client.master_id == master.id,
                Client.telegram_id == telegram_id
            ).limit(1)
        )
        client = result.scalar_one_or_none()
        if not client:
            return web.json_response({"found": False})
        return web.json_response({
            "found": True,
            "name": client.name,
            "phone": client.phone,
            "telegram_username": client.telegram_username
        })


@routes.get("/api/slots")
async def api_slots(request: web.Request):
    code = request.query.get("code")
    service_id_s = request.query.get("service")
    date_s = request.query.get("date")
    if not (code and service_id_s and date_s):
        return web.json_response({"error": "code, service, date required"}, status=400)
    try:
        service_id = int(service_id_s)
        date = datetime.strptime(date_s, "%Y-%m-%d")
    except ValueError:
        return web.json_response({"error": "bad params"}, status=400)

    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        arepo = AppointmentRepository(session)
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        service = await srepo.get_by_id(service_id)
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        # Master's timezone
        tz = pytz_timezone(master.timezone or "Europe/Moscow")
        # Respect per-date day-off list
        ws = master.work_schedule or {}
        days_off_dates = set(ws.get("days_off_dates", []))
        if date_s in days_off_dates:
            return web.json_response([])
        # Get schedule for that date
        intervals = parse_work_schedule(master.work_schedule or {}, date)
        if not intervals:
            return web.json_response([])
        # Get existing appointments that day
        start_day = datetime(date.year, date.month, date.day)
        end_day = start_day + timedelta(days=1)
        existing = await arepo.get_by_master(master.id, start_date=start_day, end_date=end_day)
        busy = [(a.start_time, a.end_time) for a in existing if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)]
        # Helper: normalize to timezone-aware UTC. If naive, treat as master's local time.
        def to_aware_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                local_dt = tz.localize(dt)
                return local_dt.astimezone(timezone.utc)
            return dt.astimezone(timezone.utc)
        # Generate slots
        slots = []
        busy_utc = [(to_aware_utc(b_start), to_aware_utc(b_end)) for b_start, b_end in busy]
        for start_t, end_t in intervals:
            # Generate base 30-min start times; compute end per service duration
            starts = generate_half_hour_slots(start_t, end_t, start_day)
            for st in starts:
                et = st + timedelta(minutes=service.duration_minutes)
                # Ensure service fits within working interval
                interval_end_dt = datetime.combine(start_day.date(), end_t)
                if et > interval_end_dt:
                    # Show slot but mark unavailable (doesn't fit before end of day)
                    st_utc = to_aware_utc(st)
                    available = st_utc > datetime.now(timezone.utc)
                    slots.append({"start": st, "end": et, "available": False if available else False})
                    continue
                st_utc = to_aware_utc(st)
                et_utc = to_aware_utc(et)
                conflict = any((st_utc < b_end and et_utc > b_start) for b_start, b_end in busy_utc)
                # Include all base starts, mark availability; hide past starts
                available = (not conflict) and (st_utc > datetime.now(timezone.utc))
                slots.append({"start": st, "end": et, "available": available})
        # Limit to first 48 half-hour slots for performance
        slots = slots[:48]
        return web.json_response([
            {"start": s["start"].isoformat(), "end": s["end"].isoformat(), "available": s["available"]}
            for s in slots
        ])


@routes.post("/api/master/schedule/days_off")
async def api_master_set_days_off(request: web.Request):
    """Update master's non-working weekdays. Body: {mid: int, days_off: ["monday", ...]}"""
    payload = await request.json()
    mid = payload.get("mid")
    days_off = payload.get("days_off") or []
    days_off_dates = payload.get("days_off_dates") or []
    if not isinstance(days_off, list):
        return web.json_response({"error": "days_off must be list"}, status=400)
    if not isinstance(days_off_dates, list):
        return web.json_response({"error": "days_off_dates must be list"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid)) if mid else None
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        # Preserve existing hours; only update days_off and days_off_dates
        ws = dict(master.work_schedule or {})
        ws["days_off"] = days_off
        # Store per-date day offs (YYYY-MM-DD strings)
        # Sanitize: keep only valid date strings
        valid_dates = []
        for ds in days_off_dates:
            try:
                datetime.strptime(ds, "%Y-%m-%d")
                valid_dates.append(ds)
            except Exception:
                pass
        ws["days_off_dates"] = valid_dates
        master.work_schedule = ws
        await mrepo.update(master)
        await session.commit()
        return web.json_response({"ok": True, "work_schedule": ws})


@routes.post("/api/master/schedule/hours")
async def api_master_set_hours(request: web.Request):
    """Update master's working hours per weekday.
    Body: {mid:int, hours: {monday:[["09:00","18:00"]], ...}}
    """
    payload = await request.json()
    mid = payload.get("mid")
    hours = payload.get("hours") or {}
    if not isinstance(hours, dict):
        return web.json_response({"error": "hours must be object"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid)) if mid else None
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        ws = master.work_schedule or {}
        # sanitize hours
        def _valid_interval(iv):
            return isinstance(iv, list) and len(iv) == 2 and all(isinstance(x, str) for x in iv)
        for key in ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]:
            ivs = hours.get(key)
            if isinstance(ivs, list):
                clean = [iv for iv in ivs if _valid_interval(iv)]
                ws[key] = clean
        master.work_schedule = ws
        await mrepo.update(master)
        await session.commit()
        return web.json_response({"ok": True, "work_schedule": ws})


@routes.post("/api/master/appointment/complete")
async def api_master_complete_appointment(request: web.Request):
    """Complete appointment: mark as completed, update client stats, record payment."""
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    client_came = payload.get("client_came")  # bool
    payment_amount = payload.get("payment_amount")  # int or None
    
    if not mid or not appointment_id or client_came is None:
        return web.json_response({"error": "mid, appointment_id, client_came required"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if not client_came:
            # Mark as no-show
            appointment.status = AppointmentStatus.NO_SHOW.value
            appointment.is_completed = True
            await arepo.update(appointment)
            await session.commit()
            return web.json_response({"ok": True, "message": "Marked as no-show"})
        
        # Client came: increment visit counter, record payment
        client = await crepo.get_by_id(appointment.client_id)
        if client:
            client.total_visits += 1
            if payment_amount is not None:
                client.total_spent += int(payment_amount)
            client.last_visit = appointment.start_time
            await crepo.update(client)
        
        appointment.status = AppointmentStatus.COMPLETED.value
        appointment.is_completed = True
        appointment.payment_amount = int(payment_amount) if payment_amount is not None else None
        await arepo.update(appointment)
        await session.commit()
        
        return web.json_response({"ok": True, "message": "Appointment completed"})


@routes.get("/api/client/appointments")
async def api_client_appointments(request: web.Request):
    """Get appointments for a client by telegram_id."""
    code = request.query.get("code")
    telegram_id = request.query.get("telegram_id")
    status_filter = request.query.get("status")  # optional: 'upcoming', 'past', 'cancelled', 'all'
    
    if not code or not telegram_id:
        return web.json_response({"error": "code and telegram_id required"}, status=400)
    
    try:
        telegram_id = int(telegram_id)
    except Exception:
        return web.json_response({"error": "invalid telegram_id"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, telegram_id)
        if not client:
            return web.json_response({"appointments": []})
        
        # Get appointments based on filter
        from datetime import datetime, timezone as dt_timezone
        from sqlalchemy import select, and_, or_
        from database.models.appointment import Appointment
        
        now = datetime.now(dt_timezone.utc)
        
        # Build query based on status filter
        conditions = [Appointment.client_id == client.id]
        
        if status_filter == "upcoming":
            # Future appointments that are not cancelled
            conditions.append(Appointment.start_time >= now)
            conditions.append(Appointment.status.in_(["scheduled", "confirmed"]))
        elif status_filter == "past":
            # Past appointments (completed or no-show)
            conditions.append(or_(
                Appointment.start_time < now,
                Appointment.status.in_(["completed", "no_show"])
            ))
        elif status_filter == "cancelled":
            # Only cancelled
            conditions.append(Appointment.status == "cancelled")
        # else: 'all' or no filter - show everything
        
        stmt = select(Appointment).where(
            and_(*conditions)
        ).order_by(Appointment.start_time.desc())
        
        res = await session.execute(stmt)
        appointments = res.scalars().all()
        
        result = []
        for app in appointments:
            service = await srepo.get_by_id(app.service_id)
            result.append({
                "id": app.id,
                "service": service.name if service else "Услуга",
                "service_id": app.service_id,
                "start": app.start_time.isoformat(),
                "end": app.end_time.isoformat(),
                "status": app.status,
                "is_completed": app.is_completed,
                "payment_amount": app.payment_amount if app.payment_amount else 0,
                "client_comment": app.client_comment if app.client_comment else "",
            })
        
        return web.json_response({"appointments": result})


@routes.post("/api/client/appointment/cancel")
async def api_client_cancel_appointment(request: web.Request):
    """Allow client to cancel their own appointment."""
    payload = await request.json()
    code = payload.get("code")
    telegram_id = payload.get("telegram_id")
    appointment_id = payload.get("appointment_id")
    
    if not all([code, telegram_id, appointment_id]):
        return web.json_response({"error": "missing fields"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, int(telegram_id))
        if not client:
            return web.json_response({"error": "client not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.client_id != client.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if appointment.status not in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
            return web.json_response({"error": "cannot cancel this appointment"}, status=400)
        
        appointment.status = AppointmentStatus.CANCELLED.value
        appointment.cancellation_reason = "Отменено клиентом"
        await arepo.update(appointment)
        
        # Cancel all reminders for this appointment
        try:
            reminder_repo = ReminderRepository(session)
            await reminder_repo.cancel_appointment_reminders(appointment.id)
        except Exception:
            pass
        
        await session.commit()
        
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            try:
                tz = pytz_timezone(tz_name)
                local_start = appointment.start_time.replace(tzinfo=timezone.utc).astimezone(tz)
                when_str = local_start.strftime('%d.%m.%Y %H:%M')
            except Exception:
                when_str = appointment.start_time.strftime('%d.%m.%Y %H:%M')
            
            service = await ServiceRepository(session).get_by_id(appointment.service_id)
            service_name = service.name if service else "Услуга"
            
            text = (
                f"❌ Клиент отменил запись\n\n"
                f"Клиент: {client.name} ({client.phone})\n"
                f"Услуга: {service_name}\n"
                f"Время: {when_str} ({tz_name})"
            )
            await bot.send_message(master.telegram_id, text)
        except Exception:
            pass
        
        return web.json_response({"ok": True})


@routes.post("/api/client/appointment/reschedule")
async def api_client_reschedule_appointment(request: web.Request):
    """Allow client to reschedule their own appointment."""
    payload = await request.json()
    code = payload.get("code")
    telegram_id = payload.get("telegram_id")
    appointment_id = payload.get("appointment_id")
    new_start_iso = payload.get("new_start")
    
    if not all([code, telegram_id, appointment_id, new_start_iso]):
        return web.json_response({"error": "missing fields"}, status=400)
    
    try:
        new_start = datetime.fromisoformat(new_start_iso)
    except Exception:
        return web.json_response({"error": "invalid date"}, status=400)
    
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        client = await crepo.get_by_telegram_id(master.id, int(telegram_id))
        if not client:
            return web.json_response({"error": "client not found"}, status=404)
        
        appointment = await arepo.get_by_id(int(appointment_id))
        if not appointment or appointment.client_id != client.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        
        if appointment.status not in [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]:
            return web.json_response({"error": "cannot reschedule this appointment"}, status=400)
        
        service = await srepo.get_by_id(appointment.service_id)
        if not service:
            return web.json_response({"error": "service not found"}, status=404)
        
        # Normalize timezone
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if new_start.tzinfo is None:
                local_dt = tz.localize(new_start)
                new_start = local_dt.astimezone(timezone.utc)
            else:
                new_start = new_start.astimezone(timezone.utc)
        except Exception:
            new_start = new_start.replace(tzinfo=timezone.utc)
        
        new_end = new_start + timedelta(minutes=service.duration_minutes)
        
        # Check conflict (excluding current appointment)
        conflict = await arepo.check_time_conflict(master.id, new_start, new_end, exclude_appointment_id=appointment.id)
        if conflict:
            return web.json_response({"error": "time slot not available"}, status=409)
        
        old_start = appointment.start_time
        appointment.start_time = new_start
        appointment.end_time = new_end
        await arepo.update(appointment)
        
        # Recreate reminders for rescheduled appointment
        try:
            await create_appointment_reminders(session, appointment, cancel_existing=True)
        except Exception:
            pass  # Don't fail reschedule if reminders fail
        
        await session.commit()
        
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            try:
                tz = pytz_timezone(tz_name)
                old_local = old_start.replace(tzinfo=timezone.utc).astimezone(tz)
                new_local = new_start.replace(tzinfo=timezone.utc).astimezone(tz)
                old_str = old_local.strftime('%d.%m.%Y %H:%M')
                new_str = new_local.strftime('%d.%m.%Y %H:%M')
            except Exception:
                old_str = old_start.strftime('%d.%m.%Y %H:%M')
                new_str = new_start.strftime('%d.%m.%Y %H:%M')
            
            # Build clickable contact link
            client_link = ""
            if client.telegram_username:
                safe_username = client.telegram_username.strip()
                if safe_username:
                    client_link = f" <a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif client.telegram_id:
                client_link = f" <a href=\"tg://user?id={client.telegram_id}\">ID:{client.telegram_id}</a>"
            
            text = (
                f"🔄 Клиент перенес запись\n\n"
                f"Клиент: {client.name}{client_link}\n"
                f"Телефон: {client.phone}\n"
                f"Услуга: {service.name}\n"
                f"Было: {old_str}\n"
                f"Стало: {new_str} ({tz_name})"
            )
            await bot.send_message(master.telegram_id, text)
        except Exception:
            pass
        
        return web.json_response({"ok": True})


@routes.post("/api/book")
async def api_book(request: web.Request):
    payload = await request.json()
    code = payload.get("code")
    service_id = payload.get("service")
    start_iso = payload.get("start")
    name = (payload.get("name") or "Клиент").strip()
    phone = (payload.get("phone") or "").strip()
    tg_id = payload.get("telegram_id")
    tg_username = payload.get("telegram_username")
    client_comment = (payload.get("client_comment") or "").strip()  # Client's comment
    if not all([code, service_id, start_iso, name, phone]):
        return web.json_response({"error": "missing fields"}, status=400)
    # Validate phone format: +7 followed by 10 digits
    if not isinstance(phone, str) or not phone.startswith('+7') or len(phone) != 12 or not phone[2:].isdigit():
        return web.json_response({"error": "bad_phone"}, status=400)
    try:
        service_id = int(service_id)
        start_dt = datetime.fromisoformat(start_iso)
    except Exception:
        return web.json_response({"error": "bad fields"}, status=400)

    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        arepo = AppointmentRepository(session)
        master = await mrepo.get_by_referral_code(code)
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        service = await srepo.get_by_id(service_id)
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        # Normalize start time to UTC: if naive, treat as master's local time
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if start_dt.tzinfo is None:
                # localize to master's tz then convert to UTC (tz-aware)
                local_dt = tz.localize(start_dt)
                start_dt = local_dt.astimezone(timezone.utc)
            else:
                # already aware: convert to UTC (tz-aware)
                start_dt = start_dt.astimezone(timezone.utc)
        except Exception:
            # fallback: mark as UTC tz-aware
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        # Compute end time for appointment
        end_dt = start_dt + timedelta(minutes=service.duration_minutes)
        if not master.is_premium:
            first_day = datetime(start_dt.year, start_dt.month, 1)
            next_month = (first_day + timedelta(days=32)).replace(day=1)
            month_apps = await arepo.get_by_master(master.id, start_date=first_day, end_date=next_month)
            month_count = sum(1 for a in month_apps if a.status in (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value, AppointmentStatus.COMPLETED.value))
            if month_count >= settings.free_max_appointments_per_month:
                return web.json_response({"error": "free_quota_exceeded"}, status=402)
        # Ensure no conflict
        conflict = await arepo.check_time_conflict(master.id, start_dt, end_dt)
        if conflict:
            return web.json_response({"error": "conflict"}, status=409)
        # Create/find client
        client = await crepo.get_by_phone(master.id, phone)
        if not client:
            client = await crepo.create(master.id, name=name, phone=phone)
        # Update Telegram info if provided (always refresh username if changed)
        updated = False
        if tg_id:
            try:
                tg_id_int = int(tg_id)
                if client.telegram_id != tg_id_int:
                    client.telegram_id = tg_id_int
                    updated = True
            except Exception:
                pass
        if tg_username:
            tg_username_str = str(tg_username).strip()
            if tg_username_str and client.telegram_username != tg_username_str:
                client.telegram_username = tg_username_str
                updated = True
        if name and client.name != name:
            client.name = name
            updated = True
        if updated:
            await crepo.update(client)
        # Create appointment
        app = await arepo.create(master.id, client.id, service.id, start_dt, end_dt)
        if client_comment:
            app.client_comment = client_comment
        await session.flush()
        
        # Create reminders for appointment
        try:
            await create_appointment_reminders(session, app, cancel_existing=False)
        except Exception:
            pass  # Don't fail booking if reminders fail
        
        await session.commit()
        # Notify master
        try:
            tz_name = master.timezone or "Europe/Moscow"
            try:
                tz = pytz_timezone(tz_name)
                local_start = start_dt.replace(tzinfo=timezone.utc).astimezone(tz)
                when_str = local_start.strftime('%d.%m.%Y %H:%M')
            except Exception:
                when_str = start_dt.strftime('%d.%m.%Y %H:%M')
            # Build clickable contact link
            client_link = ""
            if client.telegram_username:
                safe_username = client.telegram_username.strip()
                if safe_username:
                    client_link = f" <a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif client.telegram_id:
                client_link = f" <a href=\"tg://user?id={client.telegram_id}\">ID:{client.telegram_id}</a>"
            text = (
                f"🆕 Новая запись\n\n"
                f"Клиент: {client.name}{client_link}\n"
                f"Телефон: {client.phone}\n"
                f"Услуга: {service.name}\n"
                f"Время: {when_str} ({tz_name})"
            )
            if client_comment:
                text += f"\n💬 Комментарий: {client_comment}"
            await bot.send_message(master.telegram_id, text, parse_mode='HTML')
        except Exception:
            pass
        return web.json_response({"ok": True, "appointment_id": app.id})


@routes.post("/api/master/appointment/cancel")
async def api_master_cancel(request: web.Request):
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    reason = (payload.get("reason") or "").strip()
    if not (mid and appointment_id):
        return web.json_response({"error": "mid and appointment_id required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        crepo = ClientRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        app = await arepo.get_by_id(appointment_id)
        if not app or app.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        app.status = AppointmentStatus.CANCELLED.value
        session.add(app)
        
        # Cancel all reminders for this appointment
        try:
            reminder_repo = ReminderRepository(session)
            await reminder_repo.cancel_appointment_reminders(app.id)
        except Exception:
            pass
        
        await session.commit()
        # Notify master
        try:
            client = await crepo.get_by_id(app.client_id)
            service = await srepo.get_by_id(app.service_id)
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            when = app.start_time.replace(tzinfo=timezone.utc).astimezone(tz).strftime('%d.%m.%Y %H:%M')
            # clickable link
            client_link = ""
            if getattr(client, "telegram_username", None):
                safe_username = client.telegram_username.strip()
                client_link = f"<a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif getattr(client, "telegram_id", None):
                client_link = f"<a href=\"tg://user?id={client.telegram_id}\">tg id</a>"
            msg = (
                f"❌ Запись отменена\n\n"
                f"Клиент: {client.name} {client_link} ({client.phone})\n"
                f"Услуга: {service.name if service else ''}\n"
                f"Время: {when}\n"
                f"Причина: {reason or '—'}"
            )
            await bot.send_message(master.telegram_id, msg)
        except Exception:
            pass
        return web.json_response({"ok": True})


@routes.post("/api/master/appointment/reschedule")
async def api_master_reschedule(request: web.Request):
    payload = await request.json()
    mid = payload.get("mid")
    appointment_id = payload.get("appointment_id")
    new_start_iso = payload.get("new_start")
    if not (mid and appointment_id and new_start_iso):
        return web.json_response({"error": "mid, appointment_id, new_start required"}, status=400)
    try:
        new_start = datetime.fromisoformat(new_start_iso)
    except Exception:
        return web.json_response({"error": "bad new_start"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        srepo = ServiceRepository(session)
        crepo = ClientRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        app = await arepo.get_by_id(appointment_id)
        if not app or app.master_id != master.id:
            return web.json_response({"error": "appointment not found"}, status=404)
        service = await srepo.get_by_id(app.service_id)
        duration = service.duration_minutes if service else 60
        # Normalize times to UTC tz-aware
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            if new_start.tzinfo is None:
                local_dt = tz.localize(new_start)
                new_start_utc = local_dt.astimezone(timezone.utc)
            else:
                new_start_utc = new_start.astimezone(timezone.utc)
        except Exception:
            new_start_utc = new_start.replace(tzinfo=timezone.utc)
        new_end = new_start_utc + timedelta(minutes=duration)
        # Check conflict
        conflict = await arepo.check_time_conflict(master.id, new_start_utc, new_end, exclude_appointment_id=app.id)
        if conflict:
            return web.json_response({"error": "conflict"}, status=409)
        app.start_time = new_start_utc
        app.end_time = new_end
        app.status = AppointmentStatus.SCHEDULED.value
        session.add(app)
        
        # Recreate reminders for rescheduled appointment
        try:
            await create_appointment_reminders(session, app, cancel_existing=True)
        except Exception:
            pass
        
        await session.commit()
        # Notify master
        try:
            tz = pytz_timezone(master.timezone or "Europe/Moscow")
            client = await crepo.get_by_id(app.client_id)
            when = new_start.replace(tzinfo=timezone.utc).astimezone(tz).strftime('%d.%m.%Y %H:%M')
            # clickable link
            client_link = ""
            if getattr(client, "telegram_username", None):
                safe_username = client.telegram_username.strip()
                client_link = f"<a href=\"https://t.me/{safe_username}\">@{safe_username}</a>"
            elif getattr(client, "telegram_id", None):
                client_link = f"<a href=\"tg://user?id={client.telegram_id}\">tg id</a>"
            msg = (
                f"🔁 Запись перенесена\n\n"
                f"Клиент: {client.name} {client_link} ({client.phone})\n"
                f"Услуга: {service.name if service else ''}\n"
                f"Новое время: {when}"
            )
            await bot.send_message(master.telegram_id, msg)
        except Exception:
            pass
        return web.json_response({"ok": True})


@routes.get("/api/master/services")
async def api_master_services(request: web.Request):
    """Get all services for a master (including inactive)."""
    mid = request.query.get("mid")
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        services = await srepo.get_all_by_master(master.id, active_only=False)
        return web.json_response([
            {"id": s.id, "name": s.name, "price": s.price, "duration": s.duration_minutes}
            for s in services
        ])


@routes.post("/api/master/service/save")
async def api_master_service_save(request: web.Request):
    """Create or update a service."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    mid = data.get("mid")
    service_id = data.get("service_id")
    name = data.get("name", "").strip()
    price = data.get("price")
    duration = data.get("duration")
    if not mid or not name or price is None or duration is None:
        return web.json_response({"error": "mid, name, price, duration required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        if service_id:
            # Update existing
            service = await srepo.get_by_id(int(service_id))
            if not service or service.master_id != master.id:
                return web.json_response({"error": "service not found"}, status=404)
            service.name = name
            service.price = price
            service.duration_minutes = duration
        else:
            # Create new
            service = Service(
                master_id=master.id,
                name=name,
                price=price,
                duration_minutes=duration,
                is_active=True
            )
            session.add(service)
        await session.commit()
        return web.json_response({"ok": True})


@routes.post("/api/master/service/delete")
async def api_master_service_delete(request: web.Request):
    """Soft-delete a service by setting is_active=False."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    mid = data.get("mid")
    service_id = data.get("service_id")
    if not mid or not service_id:
        return web.json_response({"error": "mid, service_id required"}, status=400)
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        srepo = ServiceRepository(session)
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        service = await srepo.get_by_id(int(service_id))
        if not service or service.master_id != master.id:
            return web.json_response({"error": "service not found"}, status=404)
        service.is_active = False
        await session.commit()
        return web.json_response({"ok": True})


# ========== Expense Management APIs ==========

@routes.post("/api/master/expense/create")
async def api_master_expense_create(request: web.Request):
    """Create a new expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    category = data.get("category")
    amount = data.get("amount")
    expense_date_iso = data.get("expense_date")
    description = data.get("description", "")
    
    if not all([mid, category, amount, expense_date_iso]):
        return web.json_response({"error": "mid, category, amount, expense_date required"}, status=400)
    
    try:
        amount = int(amount)
        expense_date = datetime.fromisoformat(expense_date_iso)
    except Exception:
        return web.json_response({"error": "invalid amount or date"}, status=400)
    
    async with async_session_maker() as session:
        from database.repositories import ExpenseRepository
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.create(
            master_id=master.id,
            category=category,
            amount=amount,
            expense_date=expense_date,
            description=description
        )
        await session.commit()
        
        return web.json_response({
            "ok": True,
            "expense": {
                "id": expense.id,
                "category": expense.category,
                "amount": expense.amount,
                "expense_date": expense.expense_date.isoformat(),
                "description": expense.description
            }
        })


@routes.get("/api/master/expenses")
async def api_master_expenses(request: web.Request):
    """Get expenses for a master with optional filters."""
    mid = request.query.get("mid")
    start_date_iso = request.query.get("start_date")
    end_date_iso = request.query.get("end_date")
    category = request.query.get("category")
    
    if not mid:
        return web.json_response({"error": "mid required"}, status=400)
    
    start_date = None
    end_date = None
    
    try:
        if start_date_iso:
            start_date = datetime.fromisoformat(start_date_iso)
        if end_date_iso:
            end_date = datetime.fromisoformat(end_date_iso)
    except Exception:
        return web.json_response({"error": "invalid date format"}, status=400)
    
    async with async_session_maker() as session:
        from database.repositories import ExpenseRepository
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expenses = await erepo.get_by_master(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date,
            category=category
        )
        
        return web.json_response({
            "expenses": [
                {
                    "id": e.id,
                    "category": e.category,
                    "amount": e.amount,
                    "expense_date": e.expense_date.isoformat(),
                    "description": e.description or ""
                }
                for e in expenses
            ]
        })


@routes.post("/api/master/expense/update")
async def api_master_expense_update(request: web.Request):
    """Update an existing expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    expense_id = data.get("expense_id")
    
    if not all([mid, expense_id]):
        return web.json_response({"error": "mid and expense_id required"}, status=400)
    
    async with async_session_maker() as session:
        from database.repositories import ExpenseRepository
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.get_by_id(int(expense_id))
        if not expense or expense.master_id != master.id:
            return web.json_response({"error": "expense not found"}, status=404)
        
        # Update fields if provided
        if "category" in data:
            expense.category = data["category"]
        if "amount" in data:
            try:
                expense.amount = int(data["amount"])
            except Exception:
                return web.json_response({"error": "invalid amount"}, status=400)
        if "expense_date" in data:
            try:
                expense.expense_date = datetime.fromisoformat(data["expense_date"])
            except Exception:
                return web.json_response({"error": "invalid date"}, status=400)
        if "description" in data:
            expense.description = data["description"]
        
        await erepo.update(expense)
        await session.commit()
        
        return web.json_response({"ok": True})


@routes.post("/api/master/expense/delete")
async def api_master_expense_delete(request: web.Request):
    """Delete an expense."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    
    mid = data.get("mid")
    expense_id = data.get("expense_id")
    
    if not all([mid, expense_id]):
        return web.json_response({"error": "mid and expense_id required"}, status=400)
    
    async with async_session_maker() as session:
        from database.repositories import ExpenseRepository
        mrepo = MasterRepository(session)
        erepo = ExpenseRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        expense = await erepo.get_by_id(int(expense_id))
        if not expense or expense.master_id != master.id:
            return web.json_response({"error": "expense not found"}, status=404)
        
        await erepo.delete(int(expense_id))
        await session.commit()
        
        return web.json_response({"ok": True})


# ========== Financial Analytics APIs ==========

@routes.get("/api/master/analytics/financial")
async def api_master_analytics_financial(request: web.Request):
    """Get financial analytics for a master."""
    mid = request.query.get("mid")
    start_date_iso = request.query.get("start_date")
    end_date_iso = request.query.get("end_date")
    
    if not all([mid, start_date_iso, end_date_iso]):
        return web.json_response({"error": "mid, start_date, end_date required"}, status=400)
    
    try:
        start_date = datetime.fromisoformat(start_date_iso)
        end_date = datetime.fromisoformat(end_date_iso)
    except Exception:
        return web.json_response({"error": "invalid date format"}, status=400)
    
    async with async_session_maker() as session:
        from database.repositories import ExpenseRepository
        mrepo = MasterRepository(session)
        arepo = AppointmentRepository(session)
        erepo = ExpenseRepository(session)
        srepo = ServiceRepository(session)
        
        master = await mrepo.get_by_telegram_id(int(mid))
        if not master:
            return web.json_response({"error": "master not found"}, status=404)
        
        # Get completed appointments in period
        from sqlalchemy import select, and_, func
        from database.models.appointment import Appointment
        
        # Revenue calculation
        revenue_stmt = (
            select(func.sum(Appointment.payment_amount))
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
        )
        revenue_result = await session.execute(revenue_stmt)
        total_revenue = revenue_result.scalar() or 0
        
        # Count of completed appointments
        count_stmt = (
            select(func.count(Appointment.id))
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
        )
        count_result = await session.execute(count_stmt)
        appointments_count = count_result.scalar() or 0
        
        # Revenue by service
        revenue_by_service_stmt = (
            select(
                Appointment.service_id,
                func.sum(Appointment.payment_amount).label('total'),
                func.count(Appointment.id).label('count')
            )
            .where(
                and_(
                    Appointment.master_id == master.id,
                    Appointment.is_completed == True,
                    Appointment.start_time >= start_date,
                    Appointment.start_time <= end_date
                )
            )
            .group_by(Appointment.service_id)
            .order_by(func.sum(Appointment.payment_amount).desc())
        )
        revenue_by_service_result = await session.execute(revenue_by_service_stmt)
        revenue_by_service = []
        for row in revenue_by_service_result.all():
            service = await srepo.get_by_id(row.service_id)
            revenue_by_service.append({
                "service_name": service.name if service else "Unknown",
                "revenue": row.total or 0,
                "count": row.count
            })
        
        # Total expenses
        total_expenses = await erepo.get_total_by_period(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Expenses by category
        expenses_by_category = await erepo.get_expenses_by_category(
            master_id=master.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate profit
        profit = total_revenue - total_expenses
        
        return web.json_response({
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "revenue": {
                "total": total_revenue,
                "appointments_count": appointments_count,
                "by_service": revenue_by_service
            },
            "expenses": {
                "total": total_expenses,
                "by_category": expenses_by_category
            },
            "profit": profit
        })


async def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    # Static webapp files with cache busting
    import time
    cache_bust = str(int(time.time()))
    app.router.add_static('/webapp', path='webapp', name='webapp', append_version=True)
    app.router.add_static('/webapp-master', path='webapp-master', name='webapp-master', append_version=True)
    return app


# ========== Reminder Scheduler ==========
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.notifications import send_due_reminders
from services.incomplete_checker import check_and_notify_incomplete

reminder_scheduler = AsyncIOScheduler()


async def scan_and_send_reminders():
    """Background task to scan and send due reminders."""
    try:
        async with async_session_maker() as session:
            sent_count = await send_due_reminders(bot, session)
            if sent_count > 0:
                print(f"✅ Sent {sent_count} reminders")
    except Exception as e:
        print(f"❌ Error sending reminders: {e}")


async def check_incomplete_appointments():
    """Background task to notify masters about incomplete appointments."""
    try:
        async with async_session_maker() as session:
            await check_and_notify_incomplete(bot, session)
    except Exception as e:
        print(f"❌ Error checking incomplete appointments: {e}")


def start_reminder_scheduler():
    """Start the reminder scheduler. Runs every minute."""
    reminder_scheduler.add_job(
        scan_and_send_reminders,
        'interval',
        minutes=1,
        id='reminder_scanner',
        replace_existing=True
    )
    
    # Check incomplete appointments daily at 9:00 AM
    reminder_scheduler.add_job(
        check_incomplete_appointments,
        'cron',
        hour=9,
        minute=0,
        id='incomplete_checker',
        replace_existing=True
    )
    
    reminder_scheduler.start()
    print("📅 Reminder scheduler started (runs every 1 minute)")
    print("⏰ Incomplete appointments checker scheduled (daily at 9:00 AM)")


# ========== Text Message Handlers ==========

@dp.message(F.text)
async def handle_text_message(message: Message):
    """Handle plain text messages for schedule setup or service adding."""
    text = message.text.strip()
    
    # Check if master exists
    async with async_session_maker() as session:
        mrepo = MasterRepository(session)
        master = await mrepo.get_by_telegram_id(message.from_user.id)
        if not master:
            return  # Ignore messages from non-masters
        
        # Check if this looks like a schedule format (contains time ranges)
        # Format: ПН-ПТ 10:00-19:00; СБ-ВС 10:00-17:00
        if ':' in text and '-' in text and any(day in text.upper() for day in ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']):
            # This looks like a schedule, parse it
            try:
                was_empty = not master.work_schedule
                schedule = parse_work_schedule(text)
                master.work_schedule = schedule
                await mrepo.update(master)
                await session.commit()
                
                await message.answer("✅ График работы сохранён!")
                
                # If city is set but schedule was empty before, this completes onboarding
                if was_empty and master.city:
                    updated_master = await mrepo.get_by_telegram_id(message.from_user.id)
                    await show_setup_complete_message(message, updated_master)
                return
            except Exception as e:
                await message.answer(
                    f"❌ Не удалось распознать график работы.\n\n"
                    f"Используйте формат:\n"
                    f"<code>ПН-ПТ 10:00-19:00; СБ-ВС 10:00-17:00</code>\n\n"
                    f"Или команду /schedule для базового графика."
                )
                return
        
        # Check if this looks like a service format (contains semicolons)
        # Format: Название;Цена;Длительность
        if ';' in text:
            parts = [p.strip() for p in text.split(';')]
            if len(parts) != 3:
                await message.answer(
                    "❌ Неверный формат.\n\n"
                    "Для добавления услуги используйте:\n"
                    "<code>Название;Цена;ДлительностьМин</code>\n\n"
                    "Пример: <code>Маникюр;1500;90</code>"
                )
                return
            
            name, price_str, duration_str = parts
            try:
                price = int(price_str)
                duration = int(duration_str)
            except ValueError:
                await message.answer("❌ Цена и длительность должны быть числами.")
                return
            
            if price <= 0 or duration <= 0:
                await message.answer("❌ Цена и длительность должны быть положительными числами.")
                return
            
            srepo = ServiceRepository(session)
            service = await srepo.create(master.id, name=name, duration_minutes=duration, price=price)
            await session.commit()
            
            await message.answer(
                f"✅ Услуга добавлена:\n\n"
                f"<b>{service.name}</b>\n"
                f"Цена: {service.price} ₽\n"
                f"Длительность: {service.duration_minutes} мин"
            )
            return
        
        # If doesn't match any pattern, show help
        await message.answer(
            "ℹ️ Я не понял ваше сообщение.\n\n"
            "Вы можете:\n"
            "• Добавить услугу: <code>Название;Цена;ДлительностьМин</code>\n"
            "• Установить график: <code>ПН-ПТ 10:00-19:00; СБ-ВС 10:00-17:00</code>\n"
            "• Использовать команды: /start, /menu, /services"
        )


async def main():
    await init_db()
    app = await build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    # Start reminder scheduler
    start_reminder_scheduler()

    # Run bot polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
