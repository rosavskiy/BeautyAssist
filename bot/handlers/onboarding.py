"""
Onboarding handlers for new masters and client booking flow.
"""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.types import MenuButtonWebApp, BotCommand, BotCommandScopeChat, MenuButtonDefault
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.filters.command import CommandObject
from typing import Optional
from database.base import async_session_maker
from database.repositories.master import MasterRepository
from database.repositories.service import ServiceRepository
from database.repositories.client import ClientRepository
from database.models.master import Master
from bot.config import settings, CITY_TZ_MAP

logger = logging.getLogger(__name__)

# Will be injected during registration
bot = None

# Temporary storage for pending client links (telegram_id -> {master_id, referral_code})
# In production, consider using Redis or FSM storage
_pending_client_links: dict = {}

router = Router(name="onboarding")


def inject_bot(bot_instance):
    """Inject bot instance for this module."""
    global bot
    bot = bot_instance


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


async def set_master_commands(chat_id: int):
    """Set bot commands menu for master."""
    if not bot:
        return
    
    commands = [
        BotCommand(command="start", description="Приветствие и ссылки"),
        BotCommand(command="menu", description="Главное меню"),
        BotCommand(command="services", description="Мои услуги"),
        BotCommand(command="appointments", description="Записи на сегодня"),
        BotCommand(command="clients", description="Список клиентов"),
        BotCommand(command="finances", description="Финансы"),
        BotCommand(command="schedule", description="График работы"),
        BotCommand(command="city", description="Город/Таймзона"),
        BotCommand(command="qr_code", description="QR-код для записи"),
        BotCommand(command="subscription", description="Подписка"),
        BotCommand(command="referral", description="Реферальная программа"),
        BotCommand(command="support", description="Поддержка"),
    ]
    
    try:
        await bot.set_my_commands(
            commands=commands,
            scope=BotCommandScopeChat(chat_id=chat_id)
        )
    except Exception as e:
        logger.warning(f"Failed to set master commands: {e}")


async def show_setup_complete_message(message: Message, master: Master):
    """Show completion message after onboarding."""
    from bot.utils.webapp import build_webapp_link, build_master_webapp_link
    
    link_client = build_webapp_link(master)
    link_master = build_master_webapp_link(master)
    
    # Seed default services if needed and mark onboarding as complete
    async with async_session_maker() as session:
        await ensure_default_services(session, master)
        
        # ВАЖНО: Устанавливаем флаг завершения онбординга
        mrepo = MasterRepository(session)
        existing_master = await mrepo.get_by_id(master.id)
        if existing_master and not existing_master.is_onboarded:
            existing_master.is_onboarded = True
            await session.commit()
            logger.info(f"Master {master.id} completed onboarding")
    
    schedule_str = format_work_schedule(master.work_schedule)
    
    text = (
        "✅ <b>Профиль настроен! Можно работать!</b>\n\n"
        "📋 <b>Ваши настройки:</b>\n"
        f"• Город: {master.city}\n"
        f"• График: {schedule_str}\n\n"
        "🔗 <b>Ссылка для клиентов</b> (отправьте им):\n"
        f"{link_client or 'Укажите BOT_USERNAME в .env'}\n\n"
        "🎯 <b>Как пользоваться:</b>\n"
        "• Кнопка <b>«Кабинет»</b> слева — WebApp интерфейс\n"
        "• Введите <b>/</b> для вызова команд бота\n\n"
        "📱 <b>Доступные команды:</b>\n"
        "/menu — Главное меню\n"
        "/services — Мои услуги\n"
        "/appointments — Записи\n"
        "/clients — Клиенты\n"
        "/finances — Финансы\n"
        "/schedule — График работы\n"
        "/city — Город/Таймзона\n"
        "/qr_code — QR-код для записи\n"
        "/subscription — Подписка\n"
        "/referral — Реферальная программа\n"
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
    
    # Set bot commands for master
    await set_master_commands(message.chat.id)


@router.message(CommandStart())
async def on_start(message: Message, command: CommandObject):
    """Handle /start command for both clients and masters."""
    from bot.utils.webapp import build_webapp_url_direct, build_client_appointments_url, build_webapp_link, build_master_webapp_link
    
    # Check if this is a client booking link (has start parameter)
    start_param = command.args if command else None
    
    if start_param:
        # Check if this is a referral link
        if start_param.startswith('ref_'):
            # This is a referral link - handle master registration with referral tracking
            from services.referral import ReferralService
            
            async with async_session_maker() as session:
                referral_service = ReferralService(session)
                mrepo = MasterRepository(session)
                
                # Decode referral code
                referrer_id = ReferralService.decode_referral_code(start_param)
                
                # Check if user is already registered as master
                master = await mrepo.get_by_telegram_id(message.from_user.id)
                
                if master:
                    # Already registered - show info
                    await message.answer(
                        "Вы уже зарегистрированы как мастер!\n"
                        "Используйте /menu для доступа к функциям бота."
                    )
                    return
                
                # Create new master
                is_new_master = True
                name = (message.from_user.full_name or "Мастер").strip()
                master = await mrepo.create(
                    telegram_id=message.from_user.id,
                    name=name,
                    telegram_username=message.from_user.username,
                )
                await session.commit()
                await session.refresh(master)
                
                # Create referral record if referrer exists
                if referrer_id:
                    result = await referral_service.create_referral(
                        referrer_id=referrer_id,
                        referred_id=master.id
                    )
                    if result and result.get('success'):
                        logger.info(f"Created referral: {referrer_id} → {master.id}")
                
                # Auto-activate trial for new masters
                from database.repositories.subscription import SubscriptionRepository
                from services.payment import PaymentService
                
                sub_repo = SubscriptionRepository(session)
                if await sub_repo.is_trial_available(master.id):
                    payment_service = PaymentService(message.bot)
                    await payment_service.activate_trial(
                        master_id=master.id,
                        telegram_id=message.from_user.id,
                        session=session,
                    )
                    logger.info(f"Auto-activated trial for new master {master.id}")
                
                # Continue with onboarding flow below
                needs_setup = True
        else:
            # Client clicked booking link: show WebApp button
            # Parse referral_code and optional service_id
            parts = start_param.split('_')
            referral_code = parts[0]
            service_id = int(parts[1]) if len(parts) > 1 else None
            
            async with async_session_maker() as session:
                master = await MasterRepository(session).get_by_referral_code(referral_code)
                if not master:
                    return await message.answer("Мастер не найден")
                
                # Check if client already linked by telegram_id
                crepo = ClientRepository(session)
                existing_client = await crepo.get_by_telegram_id(master.id, message.from_user.id)
                
                webapp_url = build_webapp_url_direct(master, service_id)
                appointments_url = build_client_appointments_url(master)
                if not webapp_url:
                    return await message.answer("Ошибка конфигурации")
                
                inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Записаться к мастеру", web_app=WebAppInfo(url=webapp_url))],
                    [InlineKeyboardButton(text="📋 Мои записи", web_app=WebAppInfo(url=appointments_url))]
                ])
                
                if existing_client:
                    # Client already linked - just show booking buttons
                    await message.answer(
                        f"👋 Здравствуйте, {existing_client.name}!\n\n"
                        f"Вы уже зарегистрированы у мастера <b>{master.name}</b>.\n"
                        f"Нажмите кнопку ниже для записи.",
                        reply_markup=inline_kb,
                        parse_mode="HTML"
                    )
                else:
                    # Store referral_code for contact handler
                    # We use a simple approach: save to user's chat data via message
                    # Send contact request button
                    contact_kb = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                    
                    # Save master's referral code for later binding
                    _pending_client_links[message.from_user.id] = {
                        'master_id': master.id,
                        'referral_code': referral_code,
                        'master_name': master.name
                    }
                    
                    await message.answer(
                        f"👋 Здравствуйте!\n\n"
                        f"Вы сканировали QR-код мастера <b>{master.name}</b>.\n\n"
                        f"Чтобы привязать ваш номер и видеть историю записей, "
                        f"нажмите кнопку ниже или сразу запишитесь:",
                        reply_markup=contact_kb,
                        parse_mode="HTML"
                    )
                    
                    # Also show inline booking buttons
                    await message.answer(
                        "Или сразу запишитесь:",
                        reply_markup=inline_kb
                    )
                
                # Remove menu commands for clients (clear bot commands)
                try:
                    await bot.set_my_commands(commands=[], scope=BotCommandScopeChat(chat_id=message.chat.id))
                    await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonDefault())
                except Exception:
                    pass
                return
    
    # Master's /start command or continue after referral registration
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
            
            # Auto-activate trial for new masters
            from database.repositories.subscription import SubscriptionRepository
            from services.payment import PaymentService
            
            sub_repo = SubscriptionRepository(session)
            if await sub_repo.is_trial_available(master.id):
                payment_service = PaymentService(message.bot)
                await payment_service.activate_trial(
                    master_id=master.id,
                    telegram_id=message.from_user.id,
                    session=session,
                )
                logger.info(f"Auto-activated trial for new master {master.id}")
        
        # ЗАЩИТА: если мастер уже прошел онбординг - показать главное меню
        if master.is_onboarded and not is_new_master:
            from bot.utils.webapp import build_webapp_link, build_master_webapp_link
            
            link_client = build_webapp_link(master)
            link_master = build_master_webapp_link(master)
            
            text = (
                "👋 <b>С возвращением!</b>\n\n"
                "Вы уже настроили свой профиль.\n"
                "Используйте команды из меню для работы:\n\n"
                "📋 /menu — Главное меню\n"
                "💅 /services — Мои услуги\n"
                "📅 /appointments — Записи\n"
                "👥 /clients — Клиенты\n"
                "💰 /finances — Финансы\n"
                "🕐 /schedule — График работы\n"
                "🌍 /city — Город/Таймзона\n"
                "📱 /qr_code — QR-код для записи\n"
                "💳 /subscription — Подписка\n"
                "🎁 /referral — Реферальная программа\n"
                "💬 /support — Поддержка\n\n"
                "🔗 <b>Ссылка для клиентов:</b>\n"
                f"{link_client or 'Не настроена'}"
            )
            
            # Установить меню команд для мастера
            await set_master_commands(message.chat.id)
            
            return await message.answer(text)
        
        # Check if initial setup is needed
        needs_setup = not master.city or not master.timezone or not master.work_schedule
        
        if is_new_master or needs_setup:
            # Start onboarding flow
            welcome_text = (
                "👋 <b>Добро пожаловать в BeautyAssist!</b>\n\n"
                "Я помогу вам автоматизировать запись клиентов и управление записями.\n\n"
                "💬 Если возникнут вопросы - отправьте /support\n\n"
            )
            
            if is_new_master:
                welcome_text += (
                    "🎁 <b>Вам активирован пробный период на 30 дней!</b>\n"
                    "Все функции доступны бесплатно.\n\n"
                )
            
            welcome_text += "Давайте настроим ваш профиль за несколько шагов:"
            
            await message.answer(welcome_text)
            
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
        
        # Seed default services if empty and mark onboarding complete
        await ensure_default_services(session, master)
        
        # ВАЖНО: Устанавливаем флаг завершения онбординга
        if not master.is_onboarded:
            master.is_onboarded = True
            await mrepo.update(master)
            await session.commit()
            logger.info(f"Master {master.id} completed onboarding")
        
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
            "📱 <b>Доступные команды:</b>\n"
            "/menu — Главное меню\n"
            "/services — Мои услуги\n"
            "/appointments — Записи\n"
            "/clients — Клиенты\n"
            "/finances — Финансы\n"
            "/schedule — График работы\n"
            "/city — Город/Таймзона\n"
            "/qr_code — QR-код для записи\n"
            "/subscription — Подписка\n"
            "/referral — Реферальная программа\n"
            "/support — Поддержка\n"
        )
        await message.answer(text)
        # Set chat menu WebApp button (blue near input) to Master cabinet
        try:
            master_url = build_master_webapp_link(master)
            if master_url:
                await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(text="Кабинет", web_app=WebAppInfo(url=master_url)))
        except Exception:
            pass


@router.callback_query(F.data.startswith("setup_city:"))
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


def normalize_phone(phone: str) -> str:
    """Normalize phone number to +7XXXXXXXXXX format."""
    digits = ''.join(c for c in phone if c.isdigit())
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    if not digits.startswith('7'):
        digits = '7' + digits
    return '+' + digits


@router.message(F.contact)
async def handle_contact(message: Message):
    """Handle shared contact - link offline client to Telegram."""
    from bot.utils.webapp import build_webapp_url_direct, build_client_appointments_url
    
    contact = message.contact
    user_id = message.from_user.id
    
    # Check if this user has a pending link
    pending = _pending_client_links.pop(user_id, None)
    
    if not pending:
        # No pending link - maybe they just shared contact randomly
        await message.answer(
            "📱 Контакт получен!\n\n"
            "Чтобы привязать номер к мастеру, сначала отсканируйте QR-код мастера.",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    master_id = pending['master_id']
    master_name = pending['master_name']
    referral_code = pending['referral_code']
    
    # Normalize phone
    phone = normalize_phone(contact.phone_number)
    
    async with async_session_maker() as session:
        crepo = ClientRepository(session)
        mrepo = MasterRepository(session)
        
        master = await mrepo.get_by_id(master_id)
        if not master:
            await message.answer("Ошибка: мастер не найден", reply_markup=ReplyKeyboardRemove())
            return
        
        # Try to find existing client by phone
        existing_client = await crepo.get_by_phone(master_id, phone)
        
        if existing_client:
            # Found offline client - link Telegram!
            was_offline = existing_client.telegram_id is None
            existing_client.telegram_id = user_id
            existing_client.telegram_username = message.from_user.username
            await crepo.update(existing_client)
            await session.commit()
            
            if was_offline:
                # Count previous appointments
                from database.repositories.appointment import AppointmentRepository
                arepo = AppointmentRepository(session)
                appointments = await arepo.get_by_client(existing_client.id)
                visits_count = len([a for a in appointments if a.status in ('completed', 'confirmed', 'scheduled')])
                
                logger.info(
                    f"Linked offline client {existing_client.id} to Telegram user {user_id}. "
                    f"Previous visits: {visits_count}"
                )
                
                await message.answer(
                    f"🎉 <b>Отлично, {existing_client.name}!</b>\n\n"
                    f"Ваш номер {phone} успешно привязан.\n"
                    f"Теперь вы можете видеть историю своих записей у мастера <b>{master_name}</b>.\n\n"
                    f"📊 Найдено записей: {visits_count}",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"✅ Ваш аккаунт уже привязан, {existing_client.name}!",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="HTML"
                )
        else:
            # New client - create with Telegram info
            from database.models.client import Client
            
            name = contact.first_name or message.from_user.full_name or "Клиент"
            if contact.last_name:
                name = f"{contact.first_name} {contact.last_name}"
            
            new_client = Client(
                master_id=master_id,
                telegram_id=user_id,
                telegram_username=message.from_user.username,
                name=name,
                phone=phone,
                source="telegram_qr",  # Came via QR code
                total_visits=0,
                total_spent=0
            )
            session.add(new_client)
            await session.commit()
            await session.refresh(new_client)
            
            logger.info(f"Created new client {new_client.id} via QR code for master {master_id}")
            
            await message.answer(
                f"🎉 <b>Добро пожаловать, {name}!</b>\n\n"
                f"Вы зарегистрированы у мастера <b>{master_name}</b>.\n"
                f"Теперь вы можете записываться онлайн и получать напоминания!",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="HTML"
            )
        
        # Show booking buttons
        webapp_url = build_webapp_url_direct(master, None)
        appointments_url = build_client_appointments_url(master)
        
        if webapp_url:
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Записаться", web_app=WebAppInfo(url=webapp_url))],
                [InlineKeyboardButton(text="📋 Мои записи", web_app=WebAppInfo(url=appointments_url))]
            ])
            await message.answer(
                "Выберите действие:",
                reply_markup=inline_kb
            )


def register_handlers(dp):
    """Register onboarding handlers."""
    dp.include_router(router)
