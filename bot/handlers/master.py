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
        
        # Use webapp_base_url from settings
        base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Записи (Кабинет мастера)", 
                web_app=WebAppInfo(url=f"{base_url}/webapp-master/master.html?mid={message.from_user.id}")
            )],
            [InlineKeyboardButton(
                text="💰 Финансы", 
                web_app=WebAppInfo(url=f"{base_url}/webapp-master/finances.html?mid={message.from_user.id}")
            )],
            [InlineKeyboardButton(
                text="👥 Клиенты", 
                web_app=WebAppInfo(url=f"{base_url}/webapp/master/clients.html?mid={message.from_user.id}")
            )],
            [InlineKeyboardButton(
                text="📋 Услуги", 
                web_app=WebAppInfo(url=f"{base_url}/webapp/master/services.html?mid={message.from_user.id}")
            )],
            [InlineKeyboardButton(
                text="📱 QR-код для записи", 
                callback_data="get_qr_code"
            )],
            [InlineKeyboardButton(
                text="Открыть запись (для клиентов)", 
                web_app=WebAppInfo(url=build_webapp_url_direct(master))
            )],
        ])
        await message.answer("🎯 Главное меню", reply_markup=kb)


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
        webapp_url = f"{base_url}/webapp/master/services.html?mid={message.from_user.id}"
        
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
    """Open master appointments Mini App."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        # Create WebApp button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        
        # Use webapp_base_url from settings or fallback to localhost for development
        base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
        webapp_url = f"{base_url}/webapp-master/master.html?mid={message.from_user.id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📅 Кабинет мастера",
                web_app=WebAppInfo(url=webapp_url)
            )]
        ])
        
        await message.answer(
            "Управляйте записями через удобный интерфейс 👇",
            reply_markup=keyboard
        )


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
        webapp_url = f"{base_url}/webapp/master/clients.html?mid={message.from_user.id}"
        
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


@router.message(Command("finances"))
async def cmd_finances(message: Message):
    """Open finances Mini App."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        # Create WebApp button
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        
        # Use webapp_base_url from settings or fallback to localhost for development
        base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
        webapp_url = f"{base_url}/webapp-master/finances.html?mid={message.from_user.id}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💰 Финансы",
                web_app=WebAppInfo(url=webapp_url)
            )]
        ])
        
        await message.answer(
            "Управляйте финансами через удобный интерфейс 👇",
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


@router.message(Command("qr_code"))
async def cmd_qr_code(message: Message):
    """Generate QR code for client booking."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(message.from_user.id)
        if not master:
            return await message.answer("Нажмите /start для регистрации")
        
        try:
            from bot.utils.qr_generator import generate_webapp_qr
            from bot.utils.webapp import build_webapp_link
            from aiogram.types import BufferedInputFile
            
            # Get bot username from config
            bot_username = settings.bot_username.lstrip('@') if settings.bot_username else "beautyassist_bot"
            
            # Get booking link (same format as in onboarding)
            booking_link = build_webapp_link(master)
            
            # Generate QR code with referral code
            qr_buffer = generate_webapp_qr(bot_username=bot_username, referral_code=master.referral_code, box_size=12)
            
            # Send as photo
            photo = BufferedInputFile(qr_buffer.getvalue(), filename=f"qr_{master.referral_code}.png")
            
            await message.answer_photo(
                photo=photo,
                caption=(
                    f"📱 <b>QR-код для записи к вам</b>\n\n"
                    f"🔗 <b>Ссылка для клиентов:</b>\n"
                    f"{booking_link}\n\n"
                    f"Покажите этот код клиентам — они смогут быстро перейти к записи, "
                    f"отсканировав его камерой телефона.\n\n"
                    f"💡 <i>Сохраните изображение и используйте в соцсетях, визитках или в салоне</i>"
                ),
                parse_mode="HTML"
            )
            
        except Exception as e:
            import logging
            logging.error(f"Failed to generate QR code: {e}", exc_info=True)
            await message.answer("❌ Ошибка генерации QR-кода. Попробуйте позже.")


@router.callback_query(F.data == "get_qr_code")
async def cb_get_qr_code(call: CallbackQuery):
    """Handle QR code request from menu button."""
    async with async_session_maker() as session:
        master = await MasterRepository(session).get_by_telegram_id(call.from_user.id)
        if not master:
            await call.answer("Нажмите /start для регистрации", show_alert=True)
            return
        
        try:
            from bot.utils.qr_generator import generate_webapp_qr
            from bot.utils.webapp import build_webapp_link
            from aiogram.types import BufferedInputFile
            
            # Get bot username from config
            bot_username = settings.bot_username.lstrip('@') if settings.bot_username else "beautyassist_bot"
            
            # Get booking link (same format as in onboarding)
            booking_link = build_webapp_link(master)
            
            # Generate QR code with referral code
            qr_buffer = generate_webapp_qr(bot_username=bot_username, referral_code=master.referral_code, box_size=12)
            
            # Send as photo
            photo = BufferedInputFile(qr_buffer.getvalue(), filename=f"qr_{master.referral_code}.png")
            
            await call.message.answer_photo(
                photo=photo,
                caption=(
                    f"📱 <b>QR-код для записи к вам</b>\n\n"
                    f"🔗 <b>Ссылка для клиентов:</b>\n"
                    f"{booking_link}\n\n"
                    f"Покажите этот код клиентам — они смогут быстро перейти к записи, "
                    f"отсканировав его камерой телефона.\n\n"
                    f"💡 <i>Сохраните изображение и используйте в соцсетях, визитках или в салоне</i>"
                ),
                parse_mode="HTML"
            )
            await call.answer()
            
        except Exception as e:
            import logging
            logging.error(f"Failed to generate QR code from callback: {e}", exc_info=True)
            await call.answer("❌ Ошибка генерации QR-кода", show_alert=True)


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
