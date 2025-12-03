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
from database.repositories import MasterRepository, ServiceRepository, ClientRepository, AppointmentRepository
from database.models import Master, Service, AppointmentStatus
from bot.keyboards import get_main_menu_keyboard
from bot.utils.time_utils import get_available_dates, parse_work_schedule, generate_time_slots, parse_time, generate_half_hour_slots

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
        if not master:
            name = (message.from_user.full_name or "Мастер").strip()
            master = await mrepo.create(
                telegram_id=message.from_user.id,
                name=name,
                telegram_username=message.from_user.username,
            )
            await session.commit()
        # Seed default services if empty
        await ensure_default_services(session, master)
        link_client = build_webapp_link(master)
        link_master = build_master_webapp_link(master)
        text = (
            "Привет! Это BeautyAssist.\n\n"
            "Ссылка для клиентов (отправьте им):\n"
            f"{link_client or 'Укажите BOT_USERNAME в .env'}\n\n"
            "Команды бота:\n"
            "• /menu — открыть меню с кнопками WebApp\n"
            "• /services — список услуг (добавляйте: Название;Цена;ДлительностьМин)\n"
            "• /appointments — записи на сегодня\n"
            "• /clients — список клиентов\n"
            "• /schedule — выставить базовый график (10–19; сб-вс 10–17)\n"
            "• /city &lt;Город&gt; — установить город/таймзону (пример: /city Саратов)\n"
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
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
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
            await MasterRepository(session).update(master)
            await session.commit()
        return await message.answer("График сохранён по умолчанию (пн-пт 10-19, сб-вс 10-17). Настройте в кабинете мастера.")


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


# ========== Aiohttp App (API + Webhook + Static) ==========

routes = web.RouteTableDef()


@routes.get("/health")
async def health(_):
    from datetime import timezone
    return web.json_response({"status": "ok", "time": datetime.now(timezone.utc).isoformat()})


@routes.get("/api/master/appointments")
async def api_master_appointments(request: web.Request):
    mid = request.query.get("mid")
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
        # Today in master's local tz
        now_local = datetime.now(timezone.utc).astimezone(tz)
        start_local = tz.localize(datetime(now_local.year, now_local.month, now_local.day, 0, 0))
        end_local = start_local + timedelta(days=1)
        start_day = start_local.astimezone(timezone.utc).replace(tzinfo=None)
        end_day = end_local.astimezone(timezone.utc).replace(tzinfo=None)
        
        # Fetch today's appointments + past unprocessed
        from sqlalchemy import select, or_
        from database.models.appointment import Appointment
        stmt = select(Appointment).where(
            Appointment.master_id == master.id,
            or_(
                # Today's appointments
                (Appointment.start_time >= start_day) & (Appointment.start_time < end_day),
                # Past unprocessed (not completed and not cancelled)
                (Appointment.start_time < start_day) & (Appointment.is_completed == False) & (Appointment.status.in_(['scheduled', 'confirmed']))
            )
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
                "client": {"name": client.name, "phone": client.phone, "username": client.telegram_username},
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
        
        # Get all future and recent appointments
        from datetime import datetime, timedelta, timezone as dt_timezone
        now = datetime.now(dt_timezone.utc)
        past_cutoff = now - timedelta(days=30)  # Show appointments from last 30 days
        
        from sqlalchemy import select
        from database.models.appointment import Appointment
        stmt = select(Appointment).where(
            Appointment.client_id == client.id,
            Appointment.start_time >= past_cutoff
        ).order_by(Appointment.start_time)
        
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
        app.status = AppointmentStatus.CANCELED.value
        session.add(app)
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


async def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    # Static webapp files with cache busting
    import time
    cache_bust = str(int(time.time()))
    app.router.add_static('/webapp', path='webapp', name='webapp', append_version=True)
    app.router.add_static('/webapp-master', path='webapp-master', name='webapp-master', append_version=True)
    return app


async def main():
    await init_db()
    app = await build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    # Run bot polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
