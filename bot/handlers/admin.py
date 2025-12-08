"""Admin panel handlers."""
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.base import get_db
from database.repositories.admin import AdminRepository
from database.repositories.referral import ReferralRepository
from database.repositories.master import MasterRepository
from bot.keyboards.admin import (
    get_admin_main_menu,
    get_masters_keyboard,
    get_broadcast_keyboard,
    get_broadcast_confirm_keyboard,
    get_master_detail_keyboard,
)
from services.broadcast import BroadcastService

logger = logging.getLogger(__name__)

router = Router(name="admin")


@asynccontextmanager
async def get_admin_session():
    """Get database session for admin operations."""
    db_gen = get_db()
    session = await anext(db_gen)
    try:
        yield session
    finally:
        await db_gen.aclose()


class BroadcastStates(StatesGroup):
    """States for broadcast creation."""
    waiting_for_message = State()


class PromoCodeStates(StatesGroup):
    """States for promo code creation."""
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_discount = State()
    waiting_for_max_uses = State()
    waiting_for_valid_days = State()
    confirm = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Admin panel main command."""
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        stats = await admin_repo.get_dashboard_stats()
    
    text = (
        "🔧 <b>Админ-панель BeautyAssist</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Всего мастеров: {stats['total_masters']}\n"
        f"✅ Активных мастеров (30д): {stats['active_masters']}\n"
        f"👤 Всего клиентов: {stats['total_clients']}\n\n"
        f"📅 <b>Записи:</b>\n"
        f"Всего: {stats['total_appointments']}\n"
        f"Завершено: {stats['completed_appointments']}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"Выручка: {stats['total_revenue']:,.0f} ₽\n"
        f"Ожидается: {stats['pending_revenue']:,.0f} ₽\n"
        f"Расходы: {stats['total_expenses']:,.0f} ₽\n"
        f"Прибыль: {stats['net_profit']:,.0f} ₽"
    )
    
    await message.answer(text, reply_markup=get_admin_main_menu())


@router.message(Command("analytics"))
async def cmd_analytics(message: Message):
    """Quick access to Analytics Dashboard."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from bot.config import settings
    
    # Use webapp_base_url from settings or fallback to localhost for development
    base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
    webapp_url = f"{base_url}/webapp/admin/analytics.html"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Открыть Analytics Dashboard",
            web_app=WebAppInfo(url=webapp_url)
        )]
    ])
    
    text = (
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Интерактивная панель аналитики с графиками:\n\n"
        "📈 Retention • 👥 Cohorts • 🎯 Funnel • 📊 Growth"
    )
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "admin:menu")
async def callback_admin_menu(callback: CallbackQuery):
    """Return to admin main menu."""
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        stats = await admin_repo.get_dashboard_stats()
    
    text = (
        "🔧 <b>Админ-панель BeautyAssist</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Всего мастеров: {stats['total_masters']}\n"
        f"✅ Активных мастеров (30д): {stats['active_masters']}\n"
        f"👤 Всего клиентов: {stats['total_clients']}\n\n"
        f"📅 <b>Записи:</b>\n"
        f"Всего: {stats['total_appointments']}\n"
        f"Завершено: {stats['completed_appointments']}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"Выручка: {stats['total_revenue']:,.0f} ₽\n"
        f"Ожидается: {stats['pending_revenue']:,.0f} ₽\n"
        f"Расходы: {stats['total_expenses']:,.0f} ₽\n"
        f"Прибыль: {stats['net_profit']:,.0f} ₽"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:dashboard")
async def callback_dashboard(callback: CallbackQuery):
    """Show detailed dashboard."""
    await callback.answer("📊 Детальная аналитика в разработке")


@router.callback_query(F.data == "admin:masters")
@router.callback_query(F.data.startswith("admin:masters:page:"))
async def callback_masters_list(callback: CallbackQuery):
    """Show masters list with pagination."""
    # Parse page number
    if callback.data == "admin:masters":
        page = 0
    else:
        page = int(callback.data.split(":")[-1])
    
    limit = 10
    offset = page * limit
    
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        masters = await admin_repo.get_masters_list(
            limit=limit + 1,  # Get one extra to check if there are more pages
            offset=offset,
            filter_onboarded=True
        )
    
    has_next = len(masters) > limit
    masters = masters[:limit]  # Trim to actual limit
    
    if not masters:
        text = "👥 <b>Список мастеров</b>\n\nНет мастеров для отображения."
    else:
        text = f"👥 <b>Список мастеров</b> (страница {page + 1})\n\n"
        
        for i, master in enumerate(masters, start=offset + 1):
            premium_badge = "⭐" if master.is_premium else ""
            onboarded_badge = "✅" if master.is_onboarded else "❌"
            
            text += (
                f"{i}. {premium_badge} {master.name}\n"
                f"   {onboarded_badge} @{master.telegram_username or 'N/A'}\n"
                f"   📍 {master.city or 'Не указан'}\n"
                f"   ID: <code>{master.telegram_id}</code>\n\n"
            )
    
    await callback.message.edit_text(
        text, 
        reply_markup=get_masters_keyboard(page=page, has_next=has_next)
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def callback_broadcast_menu(callback: CallbackQuery):
    """Show broadcast menu."""
    text = (
        "📣 <b>Рассылка сообщений</b>\n\n"
        "Выберите действие:"
    )
    
    await callback.message.edit_text(text, reply_markup=get_broadcast_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast:new")
async def callback_broadcast_new(callback: CallbackQuery, state: FSMContext):
    """Start new broadcast."""
    text = (
        "📝 <b>Новая рассылка</b>\n\n"
        "Отправьте текст сообщения, которое хотите разослать всем мастерам.\n\n"
        "Поддерживается HTML-разметка:\n"
        "<code>&lt;b&gt;</code>жирный<code>&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;</code>курсив<code>&lt;/i&gt;</code>\n"
        "<code>&lt;code&gt;</code>моноширинный<code>&lt;/code&gt;</code>\n\n"
        "Отправьте /cancel для отмены."
    )
    
    await callback.message.answer(text)
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message, F.text)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast message text."""
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Рассылка отменена")
        return
    
    # Save message to state
    await state.update_data(broadcast_text=message.text)
    
    # Get recipient count
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        recipient_ids = await admin_repo.get_all_master_telegram_ids(filter_onboarded=True)
    
    recipient_count = len(recipient_ids)
    
    # Show preview
    preview_text = (
        "📋 <b>Предпросмотр рассылки</b>\n\n"
        f"Получателей: <b>{recipient_count}</b> мастеров\n\n"
        "━━━━━━━━━━━━━━━━\n"
        f"{message.text}\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "Подтвердите отправку:"
    )
    
    await message.answer(preview_text, reply_markup=get_broadcast_confirm_keyboard())


@router.callback_query(F.data == "admin:broadcast:confirm")
async def callback_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot):
    """Confirm and send broadcast."""
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    
    if not broadcast_text:
        await callback.answer("❌ Ошибка: текст сообщения не найден", show_alert=True)
        await state.clear()
        return
    
    await callback.answer("📤 Отправка началась...", show_alert=True)
    
    # Get recipients
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        recipient_ids = await admin_repo.get_all_master_telegram_ids(filter_onboarded=True)
        
        # Create broadcast record
        broadcast = await admin_repo.create_broadcast(
            content=broadcast_text,
            created_by=callback.from_user.id,
            total_recipients=len(recipient_ids),
            target_filter="onboarded"
        )
    
    # Notify admin
    await callback.message.edit_text(
        f"⏳ <b>Рассылка запущена</b>\n\n"
        f"ID: {broadcast.id}\n"
        f"Получателей: {len(recipient_ids)}\n\n"
        f"Отправка в процессе..."
    )
    
    # Send broadcast in background
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        broadcast_service = BroadcastService(bot, admin_repo)
        
        result = await broadcast_service.send_broadcast(
            broadcast_id=broadcast.id,
            content=broadcast_text,
            recipient_ids=recipient_ids
        )
    
    # Notify completion
    completion_text = (
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"ID: {broadcast.id}\n"
        f"✅ Отправлено: {result['sent']}\n"
        f"❌ Не удалось: {result['failed']}\n"
        f"📊 Всего: {result['total']}"
    )
    
    await callback.message.answer(completion_text)
    await state.clear()


@router.callback_query(F.data == "admin:broadcast:history")
async def callback_broadcast_history(callback: CallbackQuery):
    """Show broadcast history."""
    async with get_admin_session() as session:
        admin_repo = AdminRepository(session)
        broadcasts = await admin_repo.get_recent_broadcasts(limit=10)
    
    if not broadcasts:
        text = "📜 <b>История рассылок</b>\n\nРассылок пока не было."
    else:
        text = "📜 <b>История рассылок</b>\n\n"
        
        for broadcast in broadcasts:
            status = "✅" if broadcast.is_completed else "⏳"
            date = broadcast.created_at.strftime("%d.%m.%Y %H:%M")
            
            text += (
                f"{status} <b>ID {broadcast.id}</b> ({date})\n"
                f"Отправлено: {broadcast.sent_count}/{broadcast.total_recipients}\n"
                f"Не удалось: {broadcast.failed_count}\n\n"
            )
    
    await callback.message.edit_text(text, reply_markup=get_broadcast_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin:payments")
async def callback_payments(callback: CallbackQuery):
    """Show payments info (placeholder)."""
    text = (
        "💰 <b>Платежи</b>\n\n"
        "Модуль управления платежами в разработке.\n\n"
        "Планируется:\n"
        "• Просмотр всех платежей\n"
        "• Не привязанные платежи\n"
        "• Статистика по платежам"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_main_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:analytics")
async def callback_analytics(callback: CallbackQuery):
    """Open Analytics Dashboard WebApp."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from bot.config import settings
    
    # Use webapp_base_url from settings or fallback to localhost for development
    base_url = str(settings.webapp_base_url) if settings.webapp_base_url else "http://localhost:8080"
    webapp_url = f"{base_url}/webapp/admin/analytics.html"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Открыть Analytics Dashboard",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(
            text="🔙 Назад в меню",
            callback_data="admin:menu"
        )]
    ])
    
    text = (
        "📊 <b>Analytics Dashboard</b>\n\n"
        "Откройте интерактивную панель аналитики с графиками и метриками:\n\n"
        "📈 <b>Retention</b> - удержание мастеров (Day 1/7/30)\n"
        "👥 <b>Cohorts</b> - когортный анализ по неделям\n"
        "🎯 <b>Funnel</b> - воронка конверсии (5 этапов)\n"
        "📊 <b>Growth</b> - метрики роста (DAU/WAU/MAU)\n\n"
        "Нажмите кнопку ниже 👇"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:promo_codes")
async def callback_promo_codes(callback: CallbackQuery):
    """Show promo codes menu."""
    from bot.keyboards.admin import get_promo_codes_menu
    
    text = (
        "🎫 <b>Управление промокодами</b>\n\n"
        "Здесь вы можете создавать и управлять промокодами для скидок на подписки."
    )
    
    await callback.message.edit_text(text, reply_markup=get_promo_codes_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:promo:list")
async def callback_promo_list(callback: CallbackQuery):
    """Show list of promo codes."""
    async with get_admin_session() as session:
        from database.repositories.promo_code import PromoCodeRepository
        promo_repo = PromoCodeRepository(session)
        
        promo_codes = await promo_repo.get_all_promo_codes(limit=20)
    
    if not promo_codes:
        text = "🎫 <b>Промокоды</b>\n\n"
        text += "Промокоды ещё не созданы.\n"
        text += "Используйте кнопку ниже для создания."
    else:
        text = "🎫 <b>Список промокодов</b>\n\n"
        
        for promo in promo_codes:
            status_emoji = "🟢" if promo.status == "active" else "🔴"
            type_text = f"{promo.discount_percent}%" if promo.type == "percent" else f"{promo.discount_amount}₽"
            
            text += f"{status_emoji} <code>{promo.code}</code>\n"
            text += f"   💰 Скидка: {type_text}\n"
            text += f"   📊 Использовано: {promo.usage_count or 0}"
            
            if promo.max_uses:
                text += f" / {promo.max_uses}"
            
            text += "\n\n"
    
    from bot.keyboards.admin import get_promo_codes_menu
    await callback.message.edit_text(text, reply_markup=get_promo_codes_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:promo:stats")
async def callback_promo_stats(callback: CallbackQuery):
    """Show promo codes statistics."""
    async with get_admin_session() as session:
        from database.repositories.promo_code import PromoCodeRepository
        promo_repo = PromoCodeRepository(session)
        
        # Get all active promo codes with usage
        promo_codes = await promo_repo.get_all_promo_codes(status="active")
        
        total_usage = 0
        total_discount = 0.0
        
        for promo in promo_codes:
            stats = await promo_repo.get_promo_code_stats(promo.code)
            total_usage += stats.get('usage_count', 0)
            total_discount += stats.get('total_discount_given', 0)
    
    text = "📊 <b>Статистика промокодов</b>\n\n"
    text += f"🎫 Активных промокодов: {len(promo_codes)}\n"
    text += f"📈 Всего использований: {total_usage}\n"
    text += f"💰 Общая скидка: {total_discount:,.2f} ₽\n\n"
    
    if promo_codes:
        text += "<b>Топ-3 промокода:</b>\n"
        # Sort by usage
        sorted_promos = sorted(promo_codes, key=lambda p: p.usage_count or 0, reverse=True)[:3]
        
        for i, promo in enumerate(sorted_promos, 1):
            text += f"{i}. <code>{promo.code}</code> - {promo.usage_count or 0} исп.\n"
    
    from bot.keyboards.admin import get_promo_codes_menu
    await callback.message.edit_text(text, reply_markup=get_promo_codes_menu())
    await callback.answer()


@router.callback_query(F.data == "admin:promo:create")
async def callback_promo_create(callback: CallbackQuery, state: FSMContext):
    """Start promo code creation process."""
    await state.set_state(PromoCodeStates.waiting_for_code)
    
    text = (
        "➕ <b>Создание промокода - Шаг 1/5</b>\n\n"
        "Введите код промокода (например: NEWYEAR2025)\n\n"
        "<i>Требования:</i>\n"
        "• Только латинские буквы и цифры\n"
        "• От 4 до 20 символов\n"
        "• Регистр не важен (будет преобразован в UPPERCASE)\n\n"
        "Отправьте /cancel для отмены"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "admin:promo:cancel")
async def callback_promo_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel promo code creation."""
    await state.clear()
    
    text = (
        "🎫 <b>Управление промокодами</b>\n\n"
        "Создание промокода отменено."
    )
    
    from bot.keyboards.admin import get_promo_codes_menu
    await callback.message.edit_text(text, reply_markup=get_promo_codes_menu())
    await callback.answer()


@router.message(PromoCodeStates.waiting_for_code)
async def process_promo_code(message: Message, state: FSMContext):
    """Process promo code input."""
    code = message.text.strip().upper()
    
    # Validate code format
    if not code.isalnum():
        await message.answer(
            "❌ Код должен содержать только латинские буквы и цифры.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    if len(code) < 4 or len(code) > 20:
        await message.answer(
            "❌ Код должен быть от 4 до 20 символов.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    # Check if code already exists
    async with get_admin_session() as session:
        from database.repositories.promo_code import PromoCodeRepository
        promo_repo = PromoCodeRepository(session)
        existing = await promo_repo.get_promo_code_by_code(code)
        
        if existing:
            await message.answer(
                f"❌ Промокод <code>{code}</code> уже существует.\n"
                "Введите другой код или отправьте /cancel"
            )
            return
    
    # Save code and move to next step
    await state.update_data(code=code)
    await state.set_state(PromoCodeStates.waiting_for_type)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 Процент (%)", callback_data="promo_type:percent")],
        [InlineKeyboardButton(text="💰 Фиксированная сумма (₽)", callback_data="promo_type:fixed")],
        [InlineKeyboardButton(text="🎁 Бонусные дни", callback_data="promo_type:trial_extension")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    text = (
        f"➕ <b>Создание промокода - Шаг 2/5</b>\n\n"
        f"Код: <code>{code}</code>\n\n"
        f"Выберите тип скидки:"
    )
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("promo_type:"))
async def process_promo_type(callback: CallbackQuery, state: FSMContext):
    """Process promo type selection."""
    promo_type = callback.data.split(":")[1]
    await state.update_data(type=promo_type)
    await state.set_state(PromoCodeStates.waiting_for_discount)
    
    data = await state.get_data()
    
    if promo_type == "percent":
        prompt = "Введите процент скидки (например: 20)\nМаксимум: 100%"
    elif promo_type == "fixed":
        prompt = "Введите сумму скидки в рублях (например: 200)"
    else:  # trial_extension
        prompt = "Введите количество бонусных дней (например: 7)"
    
    text = (
        f"➕ <b>Создание промокода - Шаг 3/5</b>\n\n"
        f"Код: <code>{data['code']}</code>\n"
        f"Тип: {promo_type}\n\n"
        f"{prompt}\n\n"
        f"Отправьте /cancel для отмены"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(PromoCodeStates.waiting_for_discount)
async def process_promo_discount(message: Message, state: FSMContext):
    """Process discount value input."""
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Введите число.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    data = await state.get_data()
    promo_type = data['type']
    
    # Validate value
    if promo_type == "percent" and (value < 1 or value > 100):
        await message.answer(
            "❌ Процент должен быть от 1 до 100.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    if promo_type == "fixed" and value < 1:
        await message.answer(
            "❌ Сумма должна быть больше 0.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    if promo_type == "trial_extension" and (value < 1 or value > 365):
        await message.answer(
            "❌ Количество дней должно быть от 1 до 365.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    # Save value
    if promo_type == "percent":
        await state.update_data(discount_percent=value)
    elif promo_type == "fixed":
        await state.update_data(discount_amount=value)
    else:
        await state.update_data(trial_extension_days=value)
    
    await state.set_state(PromoCodeStates.waiting_for_max_uses)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾️ Без ограничений", callback_data="promo_maxuses:unlimited")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    text = (
        f"➕ <b>Создание промокода - Шаг 4/5</b>\n\n"
        f"Код: <code>{data['code']}</code>\n\n"
        f"Введите максимальное количество использований промокода\n"
        f"(например: 100) или нажмите кнопку для снятия ограничений\n\n"
        f"Отправьте /cancel для отмены"
    )
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "promo_maxuses:unlimited")
async def process_promo_maxuses_unlimited(callback: CallbackQuery, state: FSMContext):
    """Set unlimited max uses."""
    await state.update_data(max_uses=None)
    await move_to_valid_days(callback, state)


@router.message(PromoCodeStates.waiting_for_max_uses)
async def process_promo_maxuses(message: Message, state: FSMContext):
    """Process max uses input."""
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Введите число или нажмите кнопку '♾️ Без ограничений'.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    if max_uses < 1:
        await message.answer(
            "❌ Количество должно быть больше 0.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    await state.update_data(max_uses=max_uses)
    await move_to_valid_days_message(message, state)


async def move_to_valid_days(callback: CallbackQuery, state: FSMContext):
    """Helper to move to valid days step (from callback)."""
    await state.set_state(PromoCodeStates.waiting_for_valid_days)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾️ Без ограничения по времени", callback_data="promo_validdays:unlimited")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    data = await state.get_data()
    
    text = (
        f"➕ <b>Создание промокода - Шаг 5/5</b>\n\n"
        f"Код: <code>{data['code']}</code>\n\n"
        f"Введите срок действия промокода в днях\n"
        f"(например: 30) или нажмите кнопку для бессрочного промокода\n\n"
        f"Отправьте /cancel для отмены"
    )
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def move_to_valid_days_message(message: Message, state: FSMContext):
    """Helper to move to valid days step (from message)."""
    await state.set_state(PromoCodeStates.waiting_for_valid_days)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾️ Без ограничения по времени", callback_data="promo_validdays:unlimited")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")]
    ])
    
    data = await state.get_data()
    
    text = (
        f"➕ <b>Создание промокода - Шаг 5/5</b>\n\n"
        f"Код: <code>{data['code']}</code>\n\n"
        f"Введите срок действия промокода в днях\n"
        f"(например: 30) или нажмите кнопку для бессрочного промокода\n\n"
        f"Отправьте /cancel для отмены"
    )
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "promo_validdays:unlimited")
async def process_promo_validdays_unlimited(callback: CallbackQuery, state: FSMContext):
    """Set unlimited valid days."""
    await state.update_data(valid_until=None)
    await show_confirmation(callback, state, is_callback=True)


@router.message(PromoCodeStates.waiting_for_valid_days)
async def process_promo_validdays(message: Message, state: FSMContext):
    """Process valid days input."""
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Введите число или нажмите кнопку '♾️ Без ограничения по времени'.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    if days < 1:
        await message.answer(
            "❌ Количество дней должно быть больше 0.\n"
            "Попробуйте ещё раз или отправьте /cancel"
        )
        return
    
    from datetime import datetime, timedelta, timezone
    valid_until = datetime.now(timezone.utc) + timedelta(days=days)
    await state.update_data(valid_until=valid_until)
    await show_confirmation_message(message, state)


async def show_confirmation(callback: CallbackQuery, state: FSMContext, is_callback: bool = False):
    """Show confirmation screen (from callback)."""
    await state.set_state(PromoCodeStates.confirm)
    
    data = await state.get_data()
    
    # Format discount info
    if data['type'] == 'percent':
        discount_info = f"{data['discount_percent']}% скидка"
    elif data['type'] == 'fixed':
        discount_info = f"{data['discount_amount']}₽ скидка"
    else:
        discount_info = f"+{data['trial_extension_days']} дней trial"
    
    # Format limits
    max_uses_info = f"{data.get('max_uses', 'Без ограничений')}"
    if data.get('max_uses') is None:
        max_uses_info = "Без ограничений"
    
    valid_until_info = "Бессрочный"
    if data.get('valid_until'):
        valid_until_info = data['valid_until'].strftime('%d.%m.%Y')
    
    text = (
        f"✅ <b>Подтверждение создания промокода</b>\n\n"
        f"📝 Код: <code>{data['code']}</code>\n"
        f"💰 Скидка: {discount_info}\n"
        f"🔢 Макс. использований: {max_uses_info}\n"
        f"📅 Действует до: {valid_until_info}\n\n"
        f"Всё верно? Создать промокод?"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="promo_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")
        ]
    ])
    
    if is_callback:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
    else:
        await callback.answer(text, reply_markup=keyboard)


async def show_confirmation_message(message: Message, state: FSMContext):
    """Show confirmation screen (from message)."""
    await state.set_state(PromoCodeStates.confirm)
    
    data = await state.get_data()
    
    # Format discount info
    if data['type'] == 'percent':
        discount_info = f"{data['discount_percent']}% скидка"
    elif data['type'] == 'fixed':
        discount_info = f"{data['discount_amount']}₽ скидка"
    else:
        discount_info = f"+{data['trial_extension_days']} дней trial"
    
    # Format limits
    max_uses_info = f"{data.get('max_uses', 'Без ограничений')}"
    if data.get('max_uses') is None:
        max_uses_info = "Без ограничений"
    
    valid_until_info = "Бессрочный"
    if data.get('valid_until'):
        valid_until_info = data['valid_until'].strftime('%d.%m.%Y')
    
    text = (
        f"✅ <b>Подтверждение создания промокода</b>\n\n"
        f"📝 Код: <code>{data['code']}</code>\n"
        f"💰 Скидка: {discount_info}\n"
        f"🔢 Макс. использований: {max_uses_info}\n"
        f"📅 Действует до: {valid_until_info}\n\n"
        f"Всё верно? Создать промокод?"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать", callback_data="promo_confirm:yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="admin:promo:cancel")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "promo_confirm:yes")
async def process_promo_confirm(callback: CallbackQuery, state: FSMContext):
    """Create promo code in database."""
    data = await state.get_data()
    
    try:
        async with get_admin_session() as session:
            from database.repositories.promo_code import PromoCodeRepository
            from datetime import datetime, timezone
            
            promo_repo = PromoCodeRepository(session)
            
            # Prepare data
            promo_data = {
                'code': data['code'],
                'type': data['type'],
                'status': 'active',
                'valid_from': datetime.now(timezone.utc),
                'valid_until': data.get('valid_until'),
                'max_uses': data.get('max_uses')
            }
            
            if data['type'] == 'percent':
                promo_data['discount_percent'] = data['discount_percent']
            elif data['type'] == 'fixed':
                promo_data['discount_amount'] = data['discount_amount']
            else:
                promo_data['trial_extension_days'] = data['trial_extension_days']
            
            # Create promo code
            promo = await promo_repo.create_promo_code(**promo_data)
            await session.commit()
        
        text = (
            f"🎉 <b>Промокод создан успешно!</b>\n\n"
            f"Код: <code>{promo.code}</code>\n\n"
            f"Промокод активен и готов к использованию."
        )
        
        await state.clear()
        
        from bot.keyboards.admin import get_promo_codes_menu
        await callback.message.edit_text(text, reply_markup=get_promo_codes_menu())
        await callback.answer("✅ Промокод создан!")
        
    except Exception as e:
        logger.error(f"Error creating promo code: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания промокода", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("admin:promo:deactivate:"))
async def callback_promo_deactivate(callback: CallbackQuery):
    """Deactivate promo code."""
    code = callback.data.split(":", 3)[3]
    
    async with get_admin_session() as session:
        from database.repositories.promo_code import PromoCodeRepository
        promo_repo = PromoCodeRepository(session)
        
        promo = await promo_repo.get_promo_code_by_code(code)
        if promo:
            promo.status = 'inactive'
            await session.commit()
            await callback.answer(f"✅ Промокод {code} деактивирован")
        else:
            await callback.answer("❌ Промокод не найден", show_alert=True)
    
    # Refresh list
    await callback_promo_list(callback)


@router.message(Command("cancel"), PromoCodeStates)
async def cancel_promo_creation(message: Message, state: FSMContext):
    """Cancel promo code creation via /cancel command."""
    await state.clear()
    await message.answer(
        "❌ Создание промокода отменено.\n"
        "Используйте /admin для возврата в админ-панель."
    )
